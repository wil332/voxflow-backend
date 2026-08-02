web: sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
worker: celery -A app.celery_app worker --loglevel=info --concurrency=2