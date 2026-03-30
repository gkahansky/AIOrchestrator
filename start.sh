#!/bin/sh
set -e
/app/.venv/bin/python -m alembic upgrade head
exec /app/.venv/bin/uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}
