"""API FastAPI del Asistente Virtual de Trámites Académicos (despliegue en Cloud Run)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent as ag
from . import documentos, pagos
from .config import get_settings
from .data import get_datos

log = logging.getLogger("tramites")
STATIC = Path(__file__).parent / "static"
ID_PATTERN = r"^N\d{1,6}$"  # IDALUMO: "N" + hasta 6 digitos


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    get_datos()  # falla rapido si faltan los CSV
    log.info("Datos CSV cargados. Servicio listo.")
    yield


app = FastAPI(
    title="Asistente Virtual de Trámites Académicos",
    description="Agente LangChain + RAG (LlamaIndex/Elasticsearch) para Certificado de Estudios, "
                "Constancia de Matrícula y Bachiller.",
    version="2.1.0",
    lifespan=lifespan,
)


class IniciarIn(BaseModel):
    id_alumno: str = Field(pattern=ID_PATTERN, examples=["N000456"])


class ChatIn(BaseModel):
    id_alumno: str = Field(pattern=ID_PATTERN, examples=["N000456"])
    mensaje: str = Field(min_length=1, max_length=2000)


class ChatOut(BaseModel):
    id_alumno: str
    respuesta: str
    preview_url: str | None = None


def _responder(id_alumno: str, mensaje: str) -> ChatOut:
    try:
        respuesta, preview = ag.conversar(id_alumno, mensaje)
        return ChatOut(id_alumno=id_alumno, respuesta=respuesta, preview_url=preview)
    except ag.ConfiguracionIncompleta as e:
        raise HTTPException(503, str(e))
    except Exception:
        log.exception("Error procesando la conversacion")
        raise HTTPException(502, "No se pudo procesar tu consulta en este momento. Intenta nuevamente.")


# Endpoints sincronos (def): FastAPI los ejecuta en un threadpool, sin bloquear el event loop;
# agent.invoke es sincrono y cada consulta RAG abre su propia conexion a Elasticsearch.
@app.get("/health", tags=["sistema"])
def health():
    s = get_settings()
    return {
        "status": "ok",
        "openai_configurado": bool(s.openai_api_key),
        "elasticsearch_configurado": bool(s.es_url),
        "langsmith_activo": bool(s.langsmith_api_key and s.langsmith_tracing),
    }


@app.post("/sesion/iniciar", response_model=ChatOut, tags=["chat"])
def iniciar(body: IniciarIn):
    """Saluda al alumno por su nombre y presenta los trámites disponibles."""
    return _responder(body.id_alumno, ag.mensaje_inicial(body.id_alumno))


@app.post("/chat", response_model=ChatOut, tags=["chat"])
def chat(body: ChatIn):
    """Continúa la conversación (memoria por IDALUMO)."""
    return _responder(body.id_alumno, body.mensaje)


@app.get("/alumno/{id_alumno}", tags=["catalogo"])
def alumno(id_alumno: str):
    """Datos basicos del alumno para personalizar la interfaz (consulta directa a los CSV, sin LLM)."""
    import re
    if not re.match(ID_PATTERN, id_alumno):
        raise HTTPException(422, "El IDALUMO debe ser una N seguida de hasta 6 digitos.")
    fila = get_datos().alumno
    fila = fila[fila["IDALUMO"] == id_alumno]
    if fila.empty:
        raise HTTPException(404, f"No encontramos el IDALUMO {id_alumno}.")
    f = fila.iloc[0]
    return {"id_alumno": f["IDALUMO"], "nombres": f["NOMBRES"], "apellidos": f["APELLIDOS"],
            "carrera": f["DESCARRERA"], "estado": f["ESTADO"]}


@app.get("/tramites", tags=["catalogo"])
def tramites():
    """Catalogo de tramites (nombre, descripcion, precio y tiempo de entrega)."""
    return get_datos().tramites.to_dict(orient="records")


SLUG_PATTERN = r"^(certificado-estudios|constancia-matricula|bachiller)$"


@app.get("/api/preview/{slug}/{id_alumno}", tags=["preview"])
def api_preview(slug: str, id_alumno: str):
    """Datos del documento para la vista previa (solo si el alumno es elegible)."""
    import re
    if not re.match(ID_PATTERN, id_alumno):
        raise HTTPException(422, "IDALUMO invalido.")
    try:
        return documentos.construir_preview(slug, id_alumno)
    except documentos.TramiteDesconocido:
        raise HTTPException(404, "Tramite desconocido.")
    except documentos.AlumnoNoEncontrado:
        raise HTTPException(404, f"No encontramos el IDALUMO {id_alumno}.")
    except documentos.NoElegible as e:
        raise HTTPException(403, str(e))


@app.get("/preview/{slug}/{id_alumno}", include_in_schema=False)
def pagina_preview(slug: str, id_alumno: str):
    return FileResponse(STATIC / "preview.html")


class OrdenIn(BaseModel):
    tramite: str = Field(pattern=SLUG_PATTERN)
    id_alumno: str = Field(pattern=ID_PATTERN)


class PagoIn(BaseModel):
    titular: str = Field(min_length=2, max_length=80)
    numero_tarjeta: str = Field(min_length=12, max_length=23)
    vencimiento: str = Field(max_length=7)
    cvv: str = Field(max_length=4)


@app.post("/api/pagos/ordenes", tags=["pagos"])
def crear_orden(body: OrdenIn):
    """Crea (o reutiliza) la orden de pago del tramite confirmado; devuelve la URL de la pasarela."""
    try:
        p = documentos.construir_preview(body.tramite, body.id_alumno)
    except documentos.NoElegible as e:
        raise HTTPException(403, str(e))
    except (documentos.TramiteDesconocido, documentos.AlumnoNoEncontrado):
        raise HTTPException(404, "Tramite o alumno no encontrado.")
    o = pagos.crear_orden(body.tramite, body.id_alumno, p["precio"], p["tramite"])
    return {**pagos.vista(o), "tiempo_entrega": p["tiempo_entrega"], "alumno": p["alumno"]}


@app.get("/api/pagos/ordenes/{orden_id}", tags=["pagos"])
def ver_orden(orden_id: str):
    o = pagos.obtener(orden_id)
    if not o:
        raise HTTPException(404, "La orden no existe.")
    return pagos.vista(o)


@app.post("/api/pagos/ordenes/{orden_id}/pagar", tags=["pagos"])
def pagar_orden(orden_id: str, body: PagoIn):
    """Cobra en la pasarela. Los datos de tarjeta NO se guardan ni se registran en logs."""
    o, msg = pagos.pagar(orden_id, body.numero_tarjeta, body.vencimiento, body.cvv)
    if o is None:
        raise HTTPException(402, msg)
    return {**pagos.vista(o), "mensaje": msg}


@app.get("/pasarela/{orden_id}", include_in_schema=False)
def pagina_pasarela(orden_id: str):
    return FileResponse(STATIC / "pasarela.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(STATIC / "index.html")
