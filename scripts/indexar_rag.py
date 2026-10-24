"""INGESTA del RAG (LlamaIndex): carga paginas web -> SentenceSplitter -> embeddings -> Elasticsearch.
Se ejecuta UNA vez (o cuando cambie el contenido), localmente o como Cloud Run Job:
    python -m scripts.indexar_rag
Requiere OPENAI_API_KEY, ES_URL, ES_USER, ES_PASSWORD (y opcional ES_INDEX_NAME)."""
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.web import SimpleWebPageReader
from llama_index.vector_stores.elasticsearch import ElasticsearchStore

from app.config import get_settings
from app.rag import get_embeddings

FUENTES_RAG = [
    {"url": "https://contacto.upn.edu.pe/tramite-de-bachiller/que-documentos-debo-adjuntar-para-la-compra-de-carpeta-de-bachiller",
     "tramite": "bachiller"},
    {"url": "https://explora.upc.edu.pe/es_ES/79253-constancias-y-certificados",
     "tramite": "constancia_certificado"},
]


def main() -> None:
    s = get_settings()
    if not (s.openai_api_key and s.es_url):
        raise SystemExit("Faltan OPENAI_API_KEY y/o ES_URL.")
    splitter = SentenceSplitter(chunk_size=800, chunk_overlap=150)
    nodos = []
    for f in FUENTES_RAG:
        docs = SimpleWebPageReader(html_to_text=True).load_data([f["url"]])
        for d in docs:
            d.metadata["tramite"], d.metadata["fuente"] = f["tramite"], f["url"]
        n = splitter.get_nodes_from_documents(docs)
        nodos.extend(n)
        print(f"  - {f['tramite']}: {len(n)} fragmentos")
    store = ElasticsearchStore(es_url=s.es_url, es_user=s.es_user, es_password=s.es_password,
                               index_name=s.es_index_name)
    VectorStoreIndex(nodos, storage_context=StorageContext.from_defaults(vector_store=store),
                     embed_model=get_embeddings())
    print(f"✅ {len(nodos)} fragmentos indexados en '{s.es_index_name}'.")


if __name__ == "__main__":
    main()
