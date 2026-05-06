#!/bin/bash
# 小暖 CBT 启动脚本 (Linux / Railway)
set -e

echo "=== XiaoNuan CBT Starting ==="
echo "[web] Port: ${PORT:-8000}"

cd "$(dirname "$0")"
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
