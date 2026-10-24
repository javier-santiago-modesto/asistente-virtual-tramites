"""Carga de los 5 CSV (base de conocimiento estructurada) una sola vez por instancia."""
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from .config import get_settings


@dataclass(frozen=True)
class Datos:
    alumno: pd.DataFrame
    tramites: pd.DataFrame
    situacion: pd.DataFrame
    matricula: pd.DataFrame
    historial: pd.DataFrame


@lru_cache
def get_datos() -> Datos:
    d = get_settings().data_dir
    leer = lambda n: pd.read_csv(d / n, dtype=str)  # noqa: E731
    situacion = leer("situacion_academica.csv")
    situacion["CREDITOSCUMPLIDOS"] = situacion["CREDITOSCUMPLIDOS"].astype(int)
    situacion["CURSOSCOMPLETADOS"] = situacion["CURSOSCOMPLETADOS"].astype(int)
    return Datos(
        alumno=leer("alumno.csv"),
        tramites=leer("tramites.csv"),
        situacion=situacion,
        matricula=leer("matricula.csv"),
        historial=leer("historial_notas.csv"),
    )
