# Python 3.13: version mas reciente con wheels disponibles para todas las dependencias (pandas, pydantic-core, etc.)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY data ./data

# Usuario sin privilegios
RUN useradd --create-home appuser && chown -R appuser /srv
USER appuser

# Cloud Run inyecta PORT (8080 por defecto). Un solo proceso; Cloud Run escala por instancias.
ENV PORT=8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'
