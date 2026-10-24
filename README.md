# Asistente Virtual de Trámites Académicos — FastAPI en Google Cloud Run

Port del notebook *Asistente trámites académicos RAG v2.1* a un servicio web:
**FastAPI** + **Python 3.13** · LangChain (`create_agent`, 9 tools, LCEL) · LlamaIndex + Elasticsearch (RAG) · LangSmith.

## Estructura
```
app/        main.py (API) · agent.py · tools.py · rag.py · prompts.py · config.py · data.py · static/index.html (chat)
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
./deploy.sh                                              # secretos + servicio + job de indexación
gcloud run jobs execute indexar-rag-tramites --region $REGION --wait   # indexa el RAG (una vez)
```
Las claves se guardan en **Secret Manager** y se montan como variables de entorno; no están en el código ni en la imagen.

## Local
```bash
python3.13 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt pytest httpx
cp .env.example .env   # completar
uvicorn app.main:app --reload     # http://localhost:8000
pytest -q tests
```

## Limitaciones a tener en cuenta
- **Memoria `InMemorySaver`**: vive en la RAM de cada instancia y se pierde al reiniciar/escalar a cero. Por eso `deploy.sh` usa `--max-instances 1` + `--session-affinity`. Para escalar horizontalmente, cambiar el checkpointer por uno persistente (p. ej. `langgraph-checkpoint-postgres`) en `app/agent.py`.
- `--allow-unauthenticated` deja el servicio público (cada petición consume tokens de OpenAI). Para restringirlo, quítalo y usa IAM / Identity-Aware Proxy.
- Cada consulta RAG abre su propia conexión a Elasticsearch (mismo patrón que corrigió el error de event loop del notebook).
- Python 3.13 es la versión más reciente validada con todo el stack; migrar a una posterior cuando LlamaIndex/pandas publiquen soporte.
