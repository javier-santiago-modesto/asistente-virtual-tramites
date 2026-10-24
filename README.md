# Asistente Virtual de Trámites Académicos — FastAPI en Google Cloud Run

Port del notebook *Asistente trámites académicos RAG v2.1* a un servicio web:
**FastAPI** + **Python 3.13** · LangChain (`create_agent`, 9 tools, LCEL) · LlamaIndex + Elasticsearch (RAG) · LangSmith.

## Estructura
```
app/        main.py (API) · agent.py · tools.py · rag.py · prompts.py · config.py · data.py
            documentos.py (vista previa y elegibilidad) · pagos.py (órdenes y pasarela) · static/ (chat, preview, pasarela)
scripts/    indexar_rag.py  (ingesta LlamaIndex: SimpleWebPageReader → SentenceSplitter → embeddings → Elasticsearch)
data/       los 5 CSV (se incluyen en la imagen)
tests/      pruebas (reglas de negocio con los CSV reales + API)
Dockerfile · requirements.txt (versiones fijadas) · deploy.sh
```

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado y qué secretos están configurados |
| POST | `/sesion/iniciar` `{"id_alumno":"N000456"}` | Saluda por nombre y lista trámites |
| POST | `/chat` `{"id_alumno":"N000456","mensaje":"..."}` | Continúa la conversación (memoria por IDALUMO) |
| GET | `/alumno/{id}` | Datos básicos del alumno (consulta directa a los CSV, sin LLM) |
| GET | `/tramites` | Catálogo de trámites (descripción, precio y tiempo de entrega) |
| GET | `/api/preview/{slug}/{id}` | Datos de la vista previa del documento (solo si el alumno es elegible) |
| POST | `/api/pagos/ordenes` · GET `/api/pagos/ordenes/{orden}` · POST `/api/pagos/ordenes/{orden}/pagar` | Órdenes de pago y cobro en la pasarela |
| GET | `/` · `/docs` | Chat web sencillo · Swagger UI |

## Vista previa, confirmación y pago
1. El agente valida la elegibilidad y, si el alumno confirma, llama a `generar_preview_tramite`; el chat muestra un botón **Abrir vista previa**.
2. `/preview/{certificado-estudios|constancia-matricula|bachiller}/{IDALUMO}` es una página aparte con el documento y la marca de agua **Preview** (datos desde `GET /api/preview/...`, solo si el alumno es elegible).
3. **Confirmar trámite** crea una orden (`POST /api/pagos/ordenes`) y abre una ventana flotante con la información de pago.
4. **Pagar en línea** lleva a la pasarela (`/pasarela/{orden}`). Tras el pago aprobado vuelve al documento: constancia y certificado (entrega inmediata) quedan sin marca de agua y con botón de imprimir/guardar PDF; el bachiller muestra el plazo de entrega (8 días hábiles).
- **Pasarela:** por defecto es **simulada** (entorno de pruebas, no cobra ni guarda tarjetas; `4242 4242 4242 4242` aprueba, `4000 0000 0000 0002` rechaza). Para cobros reales implementa `cobrar()` de un proveedor (Culqi, Niubiz, Izipay, Stripe…) en `app/pagos.py`, preferiblemente con checkout hospedado + webhook.
- Las órdenes viven en memoria de la instancia; en producción guárdalas en una base de datos.
- El nombre de la universidad es configurable con `UNIVERSIDAD_NOMBRE`; los documentos son de demostración, sin validez oficial.

## Despliegue
Requisitos: proyecto GCP con facturación, `gcloud` autenticado, y un **Elasticsearch accesible desde Cloud Run** (Elastic Cloud, o una VM con Direct VPC egress / Serverless VPC Access).
```bash
export PROJECT_ID=mi-proyecto REGION=us-central1
export OPENAI_API_KEY=... LANGSMITH_API_KEY=... ES_URL=https://... ES_USER=elastic ES_PASSWORD=...
export ES_INDEX_NAME=tramites_academicos_rag_v2          # opcional (este es el valor por defecto)
./deploy.sh                                              # secretos + servicio + job de indexación
gcloud run jobs execute indexar-rag-tramites --region $REGION --wait   # indexa el RAG (una vez)
```
- `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `ES_URL` y `ES_PASSWORD` se guardan como secretos. `ES_USER` y `ES_INDEX_NAME` se pasan como variables de entorno normales, tanto al servicio como al job de indexación, por lo que ambos usan el mismo índice.
- Si cambias `ES_INDEX_NAME`, ejecuta de nuevo el job de indexación para crear el índice con ese nombre.
- El resto de variables (`LLM_MODEL`, `RAG_TOP_K`, `UNIVERSIDAD_NOMBRE`, etc.) usan sus valores por defecto. Para cambiarlas, añádelas a `ENVVARS` en [deploy.sh](deploy.sh). Ver la tabla de [variables de entorno](#variables-de-entorno).
Las claves se guardan en **Secret Manager** y se montan como variables de entorno; no están en el código ni en la imagen.

## Local
```bash
python3.13 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt pytest httpx
cp .env.example .env   # completar
uvicorn app.main:app --reload     # http://localhost:8000
pytest -q tests
```

## Variables de entorno
Se leen desde `.env` (local) o desde el entorno (en Cloud Run, los secretos vienen de Secret Manager). Ver [.env.example](.env.example) y [app/config.py](app/config.py).

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `OPENAI_API_KEY` | Sí (secreto) | — | Clave de OpenAI (LLM y embeddings) |
| `LANGSMITH_API_KEY` | No (secreto) | — | Activa las trazas en LangSmith si `LANGSMITH_TRACING` es true |
| `ES_URL` | Sí | — | URL del Elasticsearch del RAG |
| `ES_USER` | No | `elastic` | Usuario de Elasticsearch |
| `ES_PASSWORD` | Sí (secreto) | — | Contraseña de Elasticsearch |
| `ES_INDEX_NAME` | No | `tramites_academicos_rag_v2` | Índice de Elasticsearch donde se indexa y se consulta el RAG |
| `LANGSMITH_PROJECT` | No | `tramites-academicos-ia-generativa-rag` | Proyecto de LangSmith |
| `LANGSMITH_TRACING` | No | `true` | Habilita o deshabilita las trazas |
| `LLM_MODEL` | No | `gpt-4o-mini` | Modelo de chat del agente |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Modelo de embeddings del RAG |
| `RAG_TOP_K` | No | `4` | Fragmentos recuperados por consulta |
| `DATA_DIR` | No | `./data` | Carpeta de los CSV |
| `PERIODO_ACTUAL` | No | `2026` | Periodo académico vigente |
| `UNIVERSIDAD_NOMBRE` | No | `Universidad Inteligente` | Nombre que aparece en los documentos |
| `PAYMENT_PROVIDER` | No | `simulada` | Pasarela de pago (ver `app/pagos.py`) |

> Si cambias `ES_INDEX_NAME`, vuelve a ejecutar la indexación (`scripts/indexar_rag.py`) para que el índice exista con ese nombre.

## Costos estimados (OpenAI, `gpt-4o-mini`)
Estimación orientativa, **no medida**: precios de referencia US$ 0.15 / 1M tokens de entrada y US$ 0.60 / 1M de salida (verificar en openai.com/pricing). Cada mensaje del alumno hace ~2 llamadas al LLM; cada llamada reenvía ~3 300 tokens fijos (system prompt + esquemas de las 9 tools) más el historial.

| Por conversación | Mensajes | Tokens entrada / salida | Costo |
|---|---|---|---|
| Baja | 3 | ~25 mil / ~1 mil | ~US$ 0.004 |
| Media | 6 | ~70 mil / ~2 mil | ~US$ 0.012 |
| Alta | 10 | ~150 mil / ~3.5 mil | ~US$ 0.025 |

Ejemplo con **50 000 alumnos**:

| Conversaciones por alumno | Bajo | Medio | Alto |
|---|---|---|---|
| 5 | ~US$ 1 000 | ~US$ 3 000 | ~US$ 6 250 |
| 10 | ~US$ 2 000 | ~US$ 6 000 | ~US$ 12 500 |

- La caché automática de prompts de OpenAI puede reducir el total entre 20 y 35 %.
- A esto se suman Elasticsearch (~US$ 100–300/mes), Cloud Run (~US$ 20–100/mes) y, si se persiste la memoria, una base de datos (~US$ 30–100/mes).
- El historial se reenvía completo en cada llamada, así que el costo crece más que proporcionalmente con la longitud de la conversación. Mide los tokens reales en LangSmith con una prueba piloto antes de proyectar.

## Hoja de ruta: servidor MCP (no implementado)
Idea: exponer en `/mcp` (FastMCP, `streamable_http_app`, `stateless_http=True`) solo herramientas de **lectura y validación** reutilizando `documentos.elegibilidad`, `get_datos()` y `rag._buscar`: listar trámites, validar elegibilidad y consultar requisitos. Requisitos previos:
- **No** exponer pagos (`crear_orden`, `pagar`).
- Agregar autenticación (token Bearer o IAM de Cloud Run) antes de publicarlo: los datos de los alumnos son personales.
- Validar siempre el `IDALUMO` con `^N\d{1,6}$` y evitar herramientas que devuelvan listados masivos.

## Limitaciones a tener en cuenta
- **Memoria `InMemorySaver`**: vive en la RAM de cada instancia y se pierde al reiniciar/escalar a cero. Por eso `deploy.sh` usa `--max-instances 1` + `--session-affinity`. Para escalar horizontalmente, cambiar el checkpointer por uno persistente (p. ej. `langgraph-checkpoint-postgres`) en `app/agent.py`.
- La memoria usa el `IDALUMO` como `thread_id`: todas las conversaciones de un alumno comparten historial. Con un checkpointer persistente crecería sin límite; recorta el historial (últimos 6–8 mensajes) o usa un `thread_id` por sesión.
- `--allow-unauthenticated` deja el servicio público (cada petición consume tokens de OpenAI). Para restringirlo, quítalo y usa IAM / Identity-Aware Proxy, y añade un límite de peticiones por `IDALUMO`/IP.
- Cada consulta RAG abre su propia conexión a Elasticsearch (mismo patrón que corrigió el error de event loop del notebook).
- Python 3.13 es la versión más reciente validada con todo el stack; migrar a una posterior cuando LlamaIndex/pandas publiquen soporte.
