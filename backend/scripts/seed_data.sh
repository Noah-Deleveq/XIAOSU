#!/bin/bash
# 上传内置知识库文档（seed_docs，支持 md/txt/pdf/docx）到知识库
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python scripts/seed_upload.py
