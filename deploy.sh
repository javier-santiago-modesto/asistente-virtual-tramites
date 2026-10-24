#!/usr/bin/env bash
# Despliegue en Google Cloud Run. Uso:
#   export PROJECT_ID=mi-proyecto REGION=us-central1
#   export OPENAI_API_KEY=... LANGSMITH_API_KEY=... ES_URL=... ES_USER=elastic ES_PASSWORD=...
#   ./deploy.sh            # crea secretos, despliega servicio y job de indexacion
# Los valores se leen del entorno de tu terminal y se guardan en Secret Manager; nunca quedan en el codigo.
set -euo pipefail
: "${PROJECT_ID:?}" "${REGION:=us-central1}"
SERVICE=${SERVICE:-asistente-tramites}
JOB=${JOB:-indexar-rag-tramites}

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# 1) Secretos (crea o agrega version)
for S in OPENAI_API_KEY LANGSMITH_API_KEY ES_URL ES_PASSWORD; do
  V="${!S:?Falta la variable $S}"
  gcloud secrets describe "$S" >/dev/null 2>&1 || gcloud secrets create "$S" --replication-policy=automatic
  printf '%s' "$V" | gcloud secrets versions add "$S" --data-file=-
done

# 2) Permiso de lectura de secretos para la cuenta de servicio de Cloud Run (compute por defecto)
PN=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA="${RUN_SA:-${PN}-compute@developer.gserviceaccount.com}"
for S in OPENAI_API_KEY LANGSMITH_API_KEY ES_URL ES_PASSWORD; do
  gcloud secrets add-iam-policy-binding "$S" --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor >/dev/null
done

SECRETS="OPENAI_API_KEY=OPENAI_API_KEY:latest,LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,ES_URL=ES_URL:latest,ES_PASSWORD=ES_PASSWORD:latest"
ENVVARS="ES_USER=${ES_USER:-elastic},ES_INDEX_NAME=${ES_INDEX_NAME:-tramites_academicos_rag_v2}"

# 3) Servicio (build con Cloud Build a partir del Dockerfile)
#    max-instances=1 + session-affinity: InMemorySaver guarda la memoria en la RAM de cada instancia.
gcloud run deploy "$SERVICE" --source . --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 --timeout 300 --concurrency 20 \
  --min-instances 0 --max-instances 1 --session-affinity \
  --set-secrets "$SECRETS" --set-env-vars "$ENVVARS"

# 4) Job de indexacion RAG (ejecutar una vez, y cada vez que cambien las paginas fuente)
gcloud run jobs deploy "$JOB" --source . --region "$REGION" \
  --command python --args=-m,scripts.indexar_rag \
  --memory 2Gi --task-timeout 900 --max-retries 0 \
  --set-secrets "$SECRETS" --set-env-vars "$ENVVARS"
echo "▶ Para indexar:  gcloud run jobs execute $JOB --region $REGION --wait"
echo "▶ URL del servicio: $(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
