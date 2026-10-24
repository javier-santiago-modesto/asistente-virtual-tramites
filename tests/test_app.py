from fastapi.testclient import TestClient

from app import agent as ag
from app.main import app
from app.tools import (buscar_alumno, listar_tramites, obtener_detalle_certificado_estudios,
                       validar_bachiller_elegibilidad, validar_certificado_estudios,
                       validar_constancia_matricula)

c = TestClient(app)


def test_reglas_bachiller():
    assert validar_bachiller_elegibilidad.invoke({"id_alumno": "N000456"})["elegible"] is True
    assert validar_bachiller_elegibilidad.invoke({"id_alumno": "N001213"})["precio_tramite"] == "S/ 1,500.00"
    r = validar_bachiller_elegibilidad.invoke({"id_alumno": "N001819"})  # EGRESADO con deuda
    assert not r["elegible"] and any("biblioteca" in x for x in r["requisitos_pendientes"])
    assert not validar_bachiller_elegibilidad.invoke({"id_alumno": "N000123"})["elegible"]


def test_constancia_y_certificado():
    assert validar_constancia_matricula.invoke({"id_alumno": "N000123"})["elegible"]       # 2026
    assert not validar_constancia_matricula.invoke({"id_alumno": "N000456"})["elegible"]   # 2024
    assert validar_certificado_estudios.invoke({"id_alumno": "N000456"}) == {
        "elegible": True, "mensaje": validar_certificado_estudios.invoke({"id_alumno": "N000456"})["mensaje"]}
    assert not validar_certificado_estudios.invoke({"id_alumno": "N000123"})["elegible"]
    d = obtener_detalle_certificado_estudios.invoke({"id_alumno": "N000456"})["detalle_por_periodo"]
    assert sorted(d) == ["2023", "2024"] and len(d["2023"]) == 10


def test_buscar_y_listar():
    assert buscar_alumno.invoke({"id_alumno": "N000456"})["nombres"] == "Jose Luis"
    assert not buscar_alumno.invoke({"id_alumno": "N999999"})["encontrado"]
    assert len(listar_tramites.invoke({})) == 3
    assert listar_tramites.invoke({"nombre_tramite": "bachiller"})[0]["PRECIOTRAMITE"] == "S/ 1,500.00"


def test_health_y_ui():
    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/").status_code == 200


def test_validacion_id():
    assert c.post("/chat", json={"id_alumno": "X1", "mensaje": "hola"}).status_code == 422


def test_chat_con_agente_simulado(monkeypatch):
    class Falso:
        def invoke(self, entrada, config):
            from langchain_core.messages import AIMessage
            return {"messages": [AIMessage(content=f"[{config['configurable']['thread_id']}] ok")]}
    monkeypatch.setattr(ag, "get_agente", lambda: Falso())
    assert c.post("/sesion/iniciar", json={"id_alumno": "N000456"}).json()["respuesta"] == "[N000456] ok"
    assert c.post("/chat", json={"id_alumno": "N000456", "mensaje": "hola"}).status_code == 200


def test_sin_openai_key_503(monkeypatch):
    monkeypatch.setattr(ag, "_agente", None)
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    assert c.post("/chat", json={"id_alumno": "N000456", "mensaje": "hola"}).status_code == 503


def test_construccion_real_del_agente(monkeypatch):
    """Construye el agente real (create_agent + 9 tools) con una clave falsa, sin llamar a OpenAI."""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-fake")
    monkeypatch.setattr(ag, "_agente", None)
    assert ag.get_agente() is not None


def test_tools_rag_reciben_consulta_como_texto(monkeypatch):
    """Regresion: antes la consulta llegaba como {} (as_tool sobre RunnableLambda sin esquema)."""
    from app import tools
    vistos = []
    monkeypatch.setattr(tools, "buscar_fragmentos", lambda t, q: vistos.append((t, q)) or "ok")
    tools.obtener_requisitos_bachiller.invoke({"consulta": "requisitos de bachiller"})
    tools.consultar_info_constancia_certificado.invoke({"consulta": "que es una constancia"})
    assert vistos == [("bachiller", "requisitos de bachiller"), ("constancia_certificado", "que es una constancia")]
    assert tools.obtener_requisitos_bachiller.args_schema.model_json_schema()["required"] == ["consulta"]


def test_endpoints_catalogo_para_la_ui():
    a = c.get("/alumno/N000456").json()
    assert a["nombres"] == "JOSE LUIS" and a["estado"] == "EGRESADO"
    assert c.get("/alumno/N999999").status_code == 404
    assert c.get("/alumno/abc").status_code == 422
    assert len(c.get("/tramites").json()) == 3
    assert c.get("/static/app.js").status_code == 200 and c.get("/static/app.css").status_code == 200


# ---------------- vista previa y pagos ----------------
def test_preview_certificado_tablas():
    p = c.get("/api/preview/certificado-estudios/N000456").json()
    assert p["resumen"] == {"periodos": 2, "cursos": 20, "promedio_general": p["resumen"]["promedio_general"]}
    assert [x["periodo"] for x in p["periodos"]] == ["2023", "2024"] and len(p["periodos"][0]["cursos"]) == 10
    assert p["precio"] == 80 and p["entrega_inmediata"] is True and p["pagado"] is False


def test_preview_constancia_y_bachiller():
    k = c.get("/api/preview/constancia-matricula/N000123").json()
    assert k["periodo"] == "2026" and k["condicion"] == "MATRICULADO" and k["precio"] == 60
    b = c.get("/api/preview/bachiller/N000456").json()
    assert b["grado"] == "Bachiller en Idioma" and b["precio"] == 1500 and b["entrega_inmediata"] is False


def test_preview_no_elegible_y_errores():
    assert c.get("/api/preview/constancia-matricula/N000456").status_code == 403   # sin matricula 2026
    assert c.get("/api/preview/bachiller/N001819").status_code == 403             # deuda de biblioteca
    assert c.get("/api/preview/certificado-estudios/N001011").status_code == 403   # sin historial
    assert c.get("/api/preview/otro/N000456").status_code == 404
    assert c.get("/api/preview/bachiller/N999999").status_code == 404
    for ruta in ("/preview/bachiller/N000456", "/pasarela/XYZ"):
        assert c.get(ruta).status_code == 200


def test_flujo_de_pago():
    o = c.post("/api/pagos/ordenes", json={"tramite": "certificado-estudios", "id_alumno": "N000456"}).json()
    assert o["monto"] == 80 and o["estado"] == "pendiente" and o["checkout_url"].startswith("/pasarela/")
    oid = o["orden_id"]
    # misma orden si se vuelve a confirmar
    assert c.post("/api/pagos/ordenes", json={"tramite": "certificado-estudios", "id_alumno": "N000456"}).json()["orden_id"] == oid
    ok = {"titular": "JOSE RAMIREZ", "numero_tarjeta": "4242 4242 4242 4242", "vencimiento": "12/39", "cvv": "123"}
    assert c.post(f"/api/pagos/ordenes/{oid}/pagar", json={**ok, "numero_tarjeta": "4000 0000 0000 0002"}).status_code == 402
    assert c.post(f"/api/pagos/ordenes/{oid}/pagar", json={**ok, "numero_tarjeta": "1234 5678 9012 3456"}).status_code == 402
    assert c.post(f"/api/pagos/ordenes/{oid}/pagar", json={**ok, "vencimiento": "01/20"}).status_code == 402
    assert c.get("/api/preview/certificado-estudios/N000456").json()["pagado"] is False
    r = c.post(f"/api/pagos/ordenes/{oid}/pagar", json=ok).json()
    assert r["estado"] == "pagada" and r["return_url"] == "/preview/certificado-estudios/N000456"
    assert c.get("/api/preview/certificado-estudios/N000456").json()["pagado"] is True
    assert c.post("/api/pagos/ordenes", json={"tramite": "constancia-matricula", "id_alumno": "N000456"}).status_code == 403


def test_tool_preview_y_url_en_chat(monkeypatch):
    from app import tools
    assert tools.generar_preview_tramite.invoke({"id_alumno": "N000456", "tramite": "bachiller"})["preview_url"] == "/preview/bachiller/N000456"
    assert tools.generar_preview_tramite.invoke({"id_alumno": "N001819", "tramite": "bachiller"})["disponible"] is False

    class Falso:
        def invoke(self, e, config):
            from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
            return {"messages": [HumanMessage(content="si"),
                                 ToolMessage(content="{'preview_url': '/preview/bachiller/N000456'}", name="generar_preview_tramite", tool_call_id="1"),
                                 AIMessage(content="Listo")]}
    monkeypatch.setattr(ag, "get_agente", lambda: Falso())
    r = c.post("/chat", json={"id_alumno": "N000456", "mensaje": "si"}).json()
    assert r["preview_url"] == "/preview/bachiller/N000456"
