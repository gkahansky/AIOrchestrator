FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2 + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make src importable
ENV PYTHONPATH=/app/src

# Run Alembic migrations then start the web server
# (CMD is overridden per service in railway.toml)
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
