#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 后端依赖与测试"
cd "$ROOT/backend"
uv sync
uv run pytest -q

echo "==> 前端依赖与构建"
cd "$ROOT/web"
pnpm install
pnpm run build

echo "==> 构建完成：$ROOT/web/dist"
