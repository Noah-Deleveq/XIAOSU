#!/bin/bash
set -e
export PYTHONIOENCODING=utf-8
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/../backend"

if command -v fuser >/dev/null 2>&1; then
    fuser -k 8000/tcp >/dev/null 2>&1 || true
    sleep 1
fi

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
