#!/bin/bash
# 上传内置知识库文档（seed_docs）到知识库
set -e
cd ""/bin/../backend"
exec uv run python scripts/seed_upload.py
