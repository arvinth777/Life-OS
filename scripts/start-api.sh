#!/bin/sh
set -eu
cd "$(dirname "$0")/../backend"
alembic upgrade head
python -m app.bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
