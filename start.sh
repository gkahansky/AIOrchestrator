#!/bin/sh
set -e
if [ "$SERVICE_ROLE" = "worker" ]; then
  exec celery -A aiplatform.worker worker --loglevel=info --concurrency=2
else
  python -m alembic upgrade head
  exec uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}
fi
