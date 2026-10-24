"""Configuracion centralizada. TODOS los secretos llegan por variables de entorno
(en Cloud Run se montan desde Secret Manager); nunca se hardcodean en el codigo."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Secretos (Secret Manager -> variables de entorno) ---
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    es_url: str = ""
    es_user: str = "elastic"
    es_password: str = ""

    # --- Configuracion no secreta ---
    es_index_name: str = "tramites_academicos_rag_v2"
    langsmith_project: str = "tramites-academicos-ia-generativa-rag"
    langsmith_tracing: bool = True
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-large"
    data_dir: Path = BASE_DIR / "data"
    rag_top_k: int = 4
    periodo_actual: str = "2026"
    universidad_nombre: str = "Universidad Inteligente"
    payment_provider: str = "simulada"   # ver app/pagos.py para conectar una pasarela real


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Las librerias leen estas variables directamente del entorno.
    if s.openai_api_key:
        os.environ["OPENAI_API_KEY"] = s.openai_api_key
    if s.langsmith_api_key and s.langsmith_tracing:
        os.environ["LANGSMITH_API_KEY"] = s.langsmith_api_key
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = s.langsmith_project
    return s
