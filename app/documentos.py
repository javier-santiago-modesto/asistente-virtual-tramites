"""Datos estructurados de la VISTA PREVIA de cada documento (certificado, constancia, diploma de bachiller).
Reutiliza las mismas reglas de elegibilidad que las tools del agente; no usa el LLM."""
from datetime import date

from . import pagos, tools
from .config import get_settings
from .data import get_datos

# slug -> (nombre en tramites.csv, prefijo del codigo del documento)
TRAMITES = {
    "certificado-estudios": ("Certificado de Estudios", "CE"),
    "constancia-matricula": ("Constancia de Matricula", "CM"),
    "bachiller": ("Bachiller", "BA"),
}


class TramiteDesconocido(Exception):
    pass


class AlumnoNoEncontrado(Exception):
    pass


class NoElegible(Exception):
    pass


def elegibilidad(slug: str, id_alumno: str) -> dict:
    if slug not in TRAMITES:
        raise TramiteDesconocido(slug)
    if slug == "constancia-matricula":
        return tools._validar_constancia_matricula(id_alumno)
    if slug == "certificado-estudios":
        return tools.validar_certificado_estudios._run(id_alumno)
    return tools._validar_bachiller_elegibilidad(id_alumno)


def _condiciones(slug: str, r: dict) -> str:
    if slug == "bachiller":
        return " ".join(r.get("requisitos_pendientes", [])) or "No cumples los requisitos del Bachiller."
    return r.get("mensaje", "No eres elegible para este tramite.")


def construir_preview(slug: str, id_alumno: str) -> dict:
    nombre, prefijo = TRAMITES.get(slug, (None, None))
    if nombre is None:
        raise TramiteDesconocido(slug)
    d = get_datos()
    al = d.alumno[d.alumno["IDALUMO"] == id_alumno]
    if al.empty:
        raise AlumnoNoEncontrado(id_alumno)
    r = elegibilidad(slug, id_alumno)
    if not r.get("elegible"):
        raise NoElegible(_condiciones(slug, r))
    a = al.iloc[0]
    t = d.tramites[d.tramites["NOMBRETRAMITE"] == nombre].iloc[0]
    s = get_settings()
    hoy = date.today()
    orden = pagos.orden_pagada(id_alumno, slug)

    out = {
        "slug": slug,
        "tramite": nombre.replace("Matricula", "Matrícula"),
        "universidad": s.universidad_nombre,
        "codigo_documento": f"{prefijo}-{hoy.year}-{id_alumno}",
        "fecha_emision": hoy.isoformat(),
        "precio": int(t["PRECIOTRAMITE"]),
        "moneda": "PEN",
        "tiempo_entrega": t["TIEMPOENTREGA"],
        "entrega_inmediata": t["TIEMPOENTREGA"].strip().upper() == "INMEDIATA",
        "alumno": {
            "id": a["IDALUMO"], "nombres": a["NOMBRES"], "apellidos": a["APELLIDOS"],
            "id_carrera": a["IDCARRERA"], "carrera": a["DESCARRERA"], "estado": a["ESTADO"],
        },
        "pagado": bool(orden),
        "orden_id": orden["id"] if orden else None,
    }

    if slug == "certificado-estudios":
        h = d.historial[d.historial["IDALUMO"] == id_alumno].copy()
        h["nota"] = h["NOTACURSO"].astype(float)
        periodos = []
        for per, g in h.sort_values(["PERIODOHISTORIAL", "IDCURSO"]).groupby("PERIODOHISTORIAL"):
            periodos.append({
                "periodo": per,
                "cursos": [{"id": x.IDCURSO, "curso": x.DESCRIPCIONCURSO, "nota": float(x.nota)} for x in g.itertuples()],
                "promedio": round(float(g["nota"].mean()), 2),
            })
        out["periodos"] = periodos
        out["resumen"] = {"periodos": len(periodos), "cursos": int(len(h)), "promedio_general": round(float(h["nota"].mean()), 2)}
    elif slug == "constancia-matricula":
        out["periodo"] = r["periodo_matricula"]
        out["condicion"] = "MATRICULADO"
    else:
        sit = d.situacion[d.situacion["IDALUMO"] == id_alumno].iloc[0]
        out["creditos"] = int(sit["CREDITOSCUMPLIDOS"])
        out["cursos_completados"] = int(sit["CURSOSCOMPLETADOS"])
        out["grado"] = f"Bachiller en {a['DESCARRERA'].title()}"
    return out
