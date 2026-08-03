#!/bin/bash
set -e
celery -A app.celery_app worker --loglevel=info --concurrency=2 &
WORKER_PID=$!
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} &
API_PID=$!
wait -n $WORKER_PID $API_PID
exit 1