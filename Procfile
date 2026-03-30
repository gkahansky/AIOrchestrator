web: sh -c "python -m alembic upgrade head && uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}"
worker: celery -A aiplatform.worker worker --loglevel=info --concurrency=2
