"""Agente (LangChain create_agent) con memoria InMemorySaver. Se construye una vez por instancia."""
import re
import threading
from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from .config import get_settings
from .prompts import SYSTEM_PROMPT
from .tools import construir_tools

_agente = None
_lock = threading.Lock()


class ConfiguracionIncompleta(RuntimeError):
    pass


def get_agente():
    """Construccion perezosa y thread-safe (permite que /health responda sin claves)."""
    global _agente
    if _agente is None:
        with _lock:
            if _agente is None:
                s = get_settings()
                if not s.openai_api_key:
                    raise ConfiguracionIncompleta("Falta OPENAI_API_KEY.")
                llm = ChatOpenAI(model=s.llm_model, temperature=0, api_key=s.openai_api_key)
                _agente = create_agent(
                    model=llm,
                    tools=construir_tools(llm),
                    system_prompt=SYSTEM_PROMPT,
                    checkpointer=InMemorySaver(),  # memoria por thread_id (= IDALUMO), por instancia
                )
    return _agente


_RE_PREVIEW = re.compile(r"/preview/[a-z-]+/N\d{1,6}")


def conversar(id_alumno: str, mensaje: str, agente: Optional[object] = None):
    """Devuelve (respuesta, preview_url). preview_url sale de la tool 'generar_preview_tramite' de ESTE turno."""
    agente = agente or get_agente()
    res = agente.invoke(
        # El IDALUMO ya es conocido (sesion iniciada): se anota para que el agente no lo vuelva a pedir.
        {"messages": [HumanMessage(content=f"{mensaje}\n\n(IDALUMO del alumno en sesión: {id_alumno})")]},
        config={"configurable": {"thread_id": id_alumno}},
    )
    msgs = res["messages"]
    ultimo_humano = max((i for i, m in enumerate(msgs) if m.type == "human"), default=-1)
    preview = None
    for m in msgs[ultimo_humano + 1:]:
        if m.type == "tool" and getattr(m, "name", "") == "generar_preview_tramite":
            hit = _RE_PREVIEW.search(m.content if isinstance(m.content, str) else str(m.content))
            if hit:
                preview = hit.group(0)
    return msgs[-1].content, preview


def mensaje_inicial(id_alumno: str) -> str:
    return f"Mi IDALUMO es {id_alumno}. Salúdame solo por mis nombres (sin apellidos) y muéstrame solo los títulos de los trámites disponibles."
