"""Las 9 herramientas del agente (portadas del notebook v2.1, mismos estilos de definicion)."""
from typing import Annotated, Literal, Optional, Type

from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.tools import BaseTool, StructuredTool, tool
from pydantic import BaseModel, Field

from .config import get_settings
from .data import get_datos
from .rag import buscar_fragmentos


def soles(monto) -> str:
    """Precio en soles con dos decimales: 80 -> 'S/ 80.00'."""
    return f"S/ {float(monto):,.2f}"


# ---------------------------------------------------------------- @tool simple
@tool
def buscar_alumno(id_alumno: str) -> dict:
    """Busca los datos generales de un alumno (nombres, carrera y estado) a partir de su IDALUMO.
    Usar esta herramienta para saludar al alumno solo por sus nombres (sin apellidos) y para conocer su carrera y estado (ESTUDIANTE/EGRESADO)."""
    df = get_datos().alumno
    fila = df[df["IDALUMO"] == id_alumno]
    if fila.empty:
        return {"encontrado": False, "mensaje": f"No se encontro al alumno con IDALUMO={id_alumno}."}
    fila = fila.iloc[0]
    return {
        "encontrado": True,
        "id_alumno": fila["IDALUMO"],
        "nombres": str(fila["NOMBRES"]).title(),
        "id_carrera": fila["IDCARRERA"],
        "des_carrera": fila["DESCARRERA"],
        "estado": fila["ESTADO"],
    }


# ---------------------------------------------------------------- @tool + Annotated
@tool
def listar_tramites(
    nombre_tramite: Annotated[
        Optional[str],
        "Nombre exacto del tramite a filtrar (Certificado de Estudios, Constancia de Matricula o Bachiller). "
        "Si se deja vacio, se listan todos los tramites disponibles.",
    ] = None,
) -> list:
    """Devuelve la lista de tramites disponibles con su descripcion, precio y tiempo de entrega.
    Usar para presentarle al alumno el catalogo de tramites o el detalle de uno en particular."""
    df = get_datos().tramites
    if nombre_tramite:
        df = df[df["NOMBRETRAMITE"].str.lower() == nombre_tramite.lower()]
    df = df.assign(PRECIOTRAMITE=df["PRECIOTRAMITE"].map(soles))
    return df.to_dict(orient="records")


# ---------------------------------------------------------------- StructuredTool + args_schema
class ValidarConstanciaMatriculaInput(BaseModel):
    """Esquema de entrada para validar la elegibilidad del tramite Constancia de Matricula."""
    id_alumno: str = Field(description="IDALUMO del alumno que solicita el tramite.")


def _validar_constancia_matricula(id_alumno: str) -> dict:
    periodo = get_settings().periodo_actual
    m = get_datos().matricula
    matriculas = m[m["IDALUMO"] == id_alumno]
    actual = matriculas[matriculas["PERIODOMATRICULA"] == periodo]
    if actual.empty:
        return {
            "elegible": False,
            "mensaje": f"No estas matriculado en el periodo PERIODOMATRICULA = {periodo}, "
                       "por lo tanto no eres elegible para la Constancia de Matricula.",
        }
    fila = actual.iloc[0]
    return {"elegible": True, "id_carrera": fila["IDCARRERA"], "periodo_matricula": fila["PERIODOMATRICULA"]}


validar_constancia_matricula = StructuredTool.from_function(
    func=_validar_constancia_matricula,
    name="validar_constancia_matricula",
    description=(
        "Valida si un alumno es elegible para el tramite de Constancia de Matricula. "
        "Un alumno es elegible solo si esta matriculado en el periodo actual (PERIODOMATRICULA = 2026)."
    ),
    args_schema=ValidarConstanciaMatriculaInput,
)


# ---------------------------------------------------------------- BaseTool
class ValidarCertificadoEstudiosInput(BaseModel):
    id_alumno: str = Field(description="IDALUMO del alumno que solicita el Certificado de Estudios.")


class ValidarCertificadoEstudiosTool(BaseTool):
    """Valida UNICAMENTE la elegibilidad para el Certificado de Estudios (sin detalle de cursos/notas)."""

    name: str = "validar_certificado_estudios"
    description: str = (
        "Valida si un alumno tiene cursos y notas registrados en su historial academico (elegibilidad). "
        "Devuelve SOLO un booleano 'elegible' (sin el detalle de cursos/notas). "
        "El detalle de cursos y notas se muestra solo en la vista previa, tras la confirmacion del alumno."
    )
    args_schema: Type[BaseModel] = ValidarCertificadoEstudiosInput

    def _run(self, id_alumno: str) -> dict:
        h = get_datos().historial
        if h[h["IDALUMO"] == id_alumno].empty:
            return {
                "elegible": False,
                "mensaje": "No se encontraron cursos ni notas en tu historial academico, "
                           "por lo tanto no eres elegible para el Certificado de Estudios.",
            }
        return {
            "elegible": True,
            "mensaje": "Eres elegible para el Certificado de Estudios. Pregunta al alumno si desea "
                       "continuar antes de mostrar el detalle de cursos y notas.",
        }

    async def _arun(self, id_alumno: str) -> dict:
        return self._run(id_alumno)


validar_certificado_estudios = ValidarCertificadoEstudiosTool()


@tool
def obtener_detalle_certificado_estudios(id_alumno: str) -> dict:
    """Devuelve el detalle de cursos y notas por periodo del historial academico de un alumno.
    Usar UNICAMENTE despues de confirmar con 'validar_certificado_estudios' que el alumno es elegible
    Y de que el alumno haya CONFIRMADO explicitamente que desea continuar con el tramite. No usar esta
    tool antes de esa confirmacion."""
    h = get_datos().historial
    h = h[h["IDALUMO"] == id_alumno]
    if h.empty:
        return {"mensaje": "No se encontraron cursos ni notas en tu historial academico."}
    detalle = {
        str(p): g[["IDCURSO", "DESCRIPCIONCURSO", "NOTACURSO"]].to_dict(orient="records")
        for p, g in h.groupby("PERIODOHISTORIAL")
    }
    return {"detalle_por_periodo": detalle}


# ---------------------------------------------------------------- Workflow LCEL: RunnableParallel
def _check_creditos_cursos(id_alumno: str) -> dict:
    s = get_datos().situacion
    s = s[s["IDALUMO"] == id_alumno]
    if s.empty:
        return {"ok": False, "detalle": "Sin registro de situacion academica."}
    f = s.iloc[0]
    ok = f["CREDITOSCUMPLIDOS"] == 200 and f["CURSOSCOMPLETADOS"] == 50
    return {"ok": bool(ok), "creditos": int(f["CREDITOSCUMPLIDOS"]), "cursos": int(f["CURSOSCOMPLETADOS"])}


def _check_estado_egresado(id_alumno: str) -> dict:
    a = get_datos().alumno
    a = a[a["IDALUMO"] == id_alumno]
    if a.empty:
        return {"ok": False, "detalle": "Alumno no encontrado."}
    estado = a.iloc[0]["ESTADO"]
    return {"ok": estado == "EGRESADO", "estado": estado}


def _check_deuda_biblioteca(id_alumno: str) -> dict:
    s = get_datos().situacion
    s = s[s["IDALUMO"] == id_alumno]
    if s.empty:
        return {"ok": False, "detalle": "Sin registro de situacion academica."}
    deuda = s.iloc[0]["DEUDABIBLIOTECA"]
    return {"ok": deuda == "NO", "deuda_biblioteca": deuda}


workflow_validacion_bachiller = RunnableParallel(
    creditos_cursos=RunnableLambda(_check_creditos_cursos),
    estado=RunnableLambda(_check_estado_egresado),
    deuda_biblioteca=RunnableLambda(_check_deuda_biblioteca),
)


def _validar_bachiller_elegibilidad(id_alumno: str) -> dict:
    r = workflow_validacion_bachiller.invoke(id_alumno)
    elegible = r["creditos_cursos"]["ok"] and r["estado"]["ok"] and r["deuda_biblioteca"]["ok"]
    if elegible:
        t = get_datos().tramites
        precio = soles(t[t["NOMBRETRAMITE"] == "Bachiller"].iloc[0]["PRECIOTRAMITE"])
        return {"elegible": True, "precio_tramite": precio, "detalle": r}
    pendientes = []
    if not r["estado"]["ok"]:
        pendientes.append("Debes tener el estado ESTUDIANTE/EGRESADO = EGRESADO.")
    if not r["creditos_cursos"]["ok"]:
        pendientes.append("Debes completar 200 creditos y 50 cursos aprobados.")
    if not r["deuda_biblioteca"]["ok"]:
        pendientes.append("Debes regularizar tu deuda de biblioteca.")
    return {"elegible": False, "requisitos_pendientes": pendientes, "detalle": r}


validar_bachiller_elegibilidad = StructuredTool.from_function(
    func=_validar_bachiller_elegibilidad,
    name="validar_bachiller_elegibilidad",
    description=(
        "Valida si un alumno es elegible para el tramite de Bachiller evaluando en paralelo: "
        "(1) 200 creditos y 50 cursos completados, (2) estado EGRESADO, (3) sin deuda de biblioteca. "
        "Devuelve los requisitos pendientes si no es elegible para el trámite."
    ),
)


# ---------------------------------------------------------------- Vista previa del tramite
class GenerarPreviewInput(BaseModel):
    id_alumno: str = Field(description="IDALUMO del alumno.")
    tramite: Literal["certificado-estudios", "constancia-matricula", "bachiller"] = Field(
        description="Tramite del que se genera la vista previa.")


def _generar_preview_tramite(id_alumno: str, tramite: str) -> dict:
    from .documentos import elegibilidad  # import diferido (evita dependencia circular)
    if not elegibilidad(tramite, id_alumno).get("elegible"):
        return {"disponible": False, "mensaje": "El alumno no es elegible para este tramite; no hay vista previa."}
    return {
        "disponible": True,
        "preview_url": f"/preview/{tramite}/{id_alumno}",
        "mensaje": "Vista previa lista. La interfaz muestra al alumno un boton para abrirla en una pagina aparte, "
                   "donde confirma el tramite y paga en linea.",
    }


generar_preview_tramite = StructuredTool.from_function(
    func=_generar_preview_tramite,
    name="generar_preview_tramite",
    args_schema=GenerarPreviewInput,
    description=(
        "Habilita la VISTA PREVIA (con marca de agua 'Preview') del documento del tramite para un alumno ya "
        "validado como elegible que confirmo continuar. Se abre en una pagina aparte, donde el alumno confirma "
        "el tramite y paga en linea. Usar UNICAMENTE tras validar elegibilidad y obtener la confirmacion del alumno."
    ),
)


# ---------------------------------------------------------------- Tools RAG (puente hacia LlamaIndex)
class ConsultaRagInput(BaseModel):
    """Esquema de entrada de las tools RAG: la pregunta del alumno como texto."""
    consulta: str = Field(description="Pregunta o necesidad puntual del alumno, en lenguaje natural.")


def _rag_bachiller(consulta: str) -> str:
    return buscar_fragmentos("bachiller", consulta)


def _rag_constancia_certificado(consulta: str) -> str:
    return buscar_fragmentos("constancia_certificado", consulta)


obtener_requisitos_bachiller = StructuredTool.from_function(
    func=_rag_bachiller,
    args_schema=ConsultaRagInput,
    name="obtener_requisitos_bachiller",
    description=(
        "Consulta (via RAG / busqueda semantica en Elasticsearch) informacion oficial sobre el "
        "tramite de Bachiller: que es, documentos y requisitos que se deben adjuntar para la "
        "compra de carpeta de Bachiller, plazos, canales, etc. "
        "Se puede usar en 2 escenarios: "
        "(1) el alumno hace una pregunta o consulta GENERAL sobre Bachiller (no necesita haber "
        "validado su elegibilidad primero); o "
        "(2) como parte del flujo formal del tramite, una vez que el alumno fue validado como "
        "elegible (Regla de negocio 1.4) y confirmo que desea continuar. "
        "Recibe como entrada la pregunta o necesidad puntual del alumno."
    ),
)

consultar_info_constancia_certificado = StructuredTool.from_function(
    func=_rag_constancia_certificado,
    args_schema=ConsultaRagInput,
    name="consultar_info_constancia_certificado",
    description=(
        "Consulta (via RAG / busqueda semantica en Elasticsearch) informacion oficial general "
        "sobre CONSTANCIA DE MATRICULA y CERTIFICADO DE ESTUDIOS (que son, como se solicitan en "
        "general, plazos, canales, preguntas frecuentes, etc.). Usar UNICAMENTE cuando el alumno "
        "hace una pregunta o consulta GENERAL sobre estos 2 tramites que NO sea una solicitud de "
        "validar su elegibilidad ni de generar su documento. Recibe como entrada la pregunta del alumno.\n\n"
        "NO usar esta tool para:\n"
        "- Validar elegibilidad (usar 'validar_constancia_matricula' o 'validar_certificado_estudios').\n"
        "- Generar el documento oficial del alumno (usar 'generar_preview_tramite').\n"
        "- Preguntas sobre el tramite de Bachiller (para eso usar 'obtener_requisitos_bachiller')."
    ),
)


def construir_tools(llm) -> list:
    return [
        buscar_alumno,
        listar_tramites,
        validar_constancia_matricula,
        validar_certificado_estudios,
        validar_bachiller_elegibilidad,
        generar_preview_tramite,
        obtener_requisitos_bachiller,
        consultar_info_constancia_certificado,
    ]
