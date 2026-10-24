"""RAG con LlamaIndex + Elasticsearch: RECUPERACION (la ingesta esta en scripts/indexar_rag.py)."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from langchain_core.runnables import RunnableLambda
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.elasticsearch import ElasticsearchStore

from .config import get_settings


@lru_cache
def get_embeddings() -> OpenAIEmbedding:
    s = get_settings()
    return OpenAIEmbedding(model=s.embedding_model, api_key=s.openai_api_key or None)


def format_nodes(nodes) -> str:
    if not nodes:
        return "No se encontro informacion relevante en la base de conocimiento."
    partes = [f"{n.node.get_content()}\n(Fuente: {n.node.metadata.get('fuente', '')})" for n in nodes]
    return "\n\n---\n\n".join(partes)


log = logging.getLogger("tramites.rag")


def _buscar(tramite: str, query: str) -> str:
    """Abre una conexion FRESCA a Elasticsearch por consulta (evita el error
    'Timeout context manager should be used inside a task' del cliente async
    cuando se reutiliza entre peticiones/hilos distintos)."""
    s = get_settings()
    if not s.es_url:
        return "El servicio de busqueda (Elasticsearch) no esta configurado."
    store = ElasticsearchStore(
        es_url=s.es_url, es_user=s.es_user, es_password=s.es_password, index_name=s.es_index_name
    )
    index = VectorStoreIndex.from_vector_store(vector_store=store, embed_model=get_embeddings())
    filtro = MetadataFilters(filters=[MetadataFilter(key="tramite", value=tramite)])
    retriever = index.as_retriever(similarity_top_k=s.rag_top_k, filters=filtro)
    return format_nodes(retriever.retrieve(query))


def _en_hilo_limpio(fn, *args):
    """Ejecuta fn en un hilo NUEVO con su propio event loop (sin loop en ejecucion).
    El cliente async de Elasticsearch que usa LlamaIndex falla si la consulta se hace desde
    hilos de FastAPI/LangGraph sin loop propio; este es el mismo escenario que funciona
    en scripts/probar_rag.py (hilo principal, sin loop activo)."""
    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return fn(*args)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(runner).result()


def buscar_fragmentos(tramite: str, query: str) -> str:
    """Envuelve la busqueda: si Elasticsearch falla, registra el error COMPLETO en el log del
    servidor y devuelve un mensaje explicito (en vez de ocultarlo como 'sin informacion')."""
    try:
        return _en_hilo_limpio(_buscar, tramite, query)
    except Exception as e:
        log.exception("Fallo la busqueda RAG (tramite=%s)", tramite)
        return f"ERROR_TECNICO_RAG: no se pudo consultar la base de conocimiento ({type(e).__name__}: {e})."


cadena_rag_bachiller = RunnableLambda(lambda q: buscar_fragmentos("bachiller", q))
cadena_rag_constancia_certificado = RunnableLambda(lambda q: buscar_fragmentos("constancia_certificado", q))
