# Backend-only persistent container image for Bottom Pot FastAPI + BoardMonitor (Option 1 split deploy)
# Deploy frontend/ separately on Vercel with VITE_API_BASE_URL pointing to this service's HTTPS URL.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    BOTTOM_POT_DATA_DIR=/data \
    BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 \
    MONITORING_ENABLED=true \
    SERPER_MODE=fallback \
    TRUST_PROXY_HEADERS=true

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"

CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
