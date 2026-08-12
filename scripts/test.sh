#!/bin/bash
# 运行后端测试
set -e
cd "$(dirname "$0")/../backend"
exec uv run pytest "$@"
