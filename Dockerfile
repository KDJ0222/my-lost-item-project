FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATA_DIR=/data \
    PORT=8000

WORKDIR /app
COPY requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app:app /data

# Explicit source allowlist: never bake .env, a local DB, or uploaded photos into the image.
COPY main.py config.py database.py models.py schemas.py ./
COPY routers/ ./routers/
COPY services/ ./services/
COPY templates/index.html ./templates/index.html
COPY static/css/ ./static/css/
COPY static/js/ ./static/js/
COPY static/vendor/ ./static/vendor/
COPY scripts/start_server.py scripts/data_backup.py scripts/smoke_gemini.py ./scripts/

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health', timeout=3).read()"
CMD ["python", "-m", "scripts.start_server"]
