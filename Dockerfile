FROM python:3.12-slim-bookworm

WORKDIR /app

# System deps for psycopg2 + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY . .

# Make src importable
ENV PYTHONPATH=/app/src
# Point marketing audit pipeline at the vendored submodule
ENV AI_MARKETING_CLAUDE_PATH=/app/vendor/ai-marketing-claude

# Run Alembic migrations then start the web server
# (CMD is overridden per service in railway.toml)
CMD ["sh", "-c", "if [ \"$SERVICE_ROLE\" = \"worker\" ]; then exec celery -A aiplatform.worker worker --loglevel=info --concurrency=2; else python -m alembic upgrade head && exec uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
