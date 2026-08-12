#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

(
  cd "$ROOT/backend"
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

cd "$ROOT/web"
exec pnpm run dev -- --host 0.0.0.0
