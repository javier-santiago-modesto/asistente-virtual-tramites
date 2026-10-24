"""Diagnostico del RAG sin pasar por el LLM:  python -m scripts.probar_rag "requisitos de bachiller"
Muestra la configuracion, cuantos documentos hay en el indice y los fragmentos recuperados."""
import sys

from elasticsearch import Elasticsearch

from app.config import get_settings
from app.rag import _buscar

s = get_settings()
q = " ".join(sys.argv[1:]) or "requisitos para el tramite de bachiller"
print(f"ES_URL={s.es_url!r}  indice={s.es_index_name!r}  openai_key={'si' if s.openai_api_key else 'NO'}")
es = Elasticsearch(s.es_url, basic_auth=(s.es_user, s.es_password))
print("conexion ES:", es.ping())
print("docs en el indice:", es.count(index=s.es_index_name)["count"])
hit = es.search(index=s.es_index_name, size=1)["hits"]["hits"]
if hit:
    print("campos de un documento:", list(hit[0]["_source"].keys()))
    print("metadata:", hit[0]["_source"].get("metadata"))
for t in ("bachiller", "constancia_certificado"):
    print(f"\n=== RAG tramite={t} | consulta={q!r} ===")
    print(_buscar(t, q)[:1200])
