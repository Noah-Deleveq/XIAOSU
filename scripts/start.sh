#!/bin/bash
# 一键启动后端服务（uv 管理依赖）
set -e
cd "$(dirname "$0")/../backend"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
