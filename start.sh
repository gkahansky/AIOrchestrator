#!/bin/sh
set -e
PYTHONPATH=/app/src python -m alembic upgrade head
exec PYTHONPATH=/app/src python -m uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}
