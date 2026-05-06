#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== XiaoNuan CBT ==="
echo "PORT=${PORT:-8000}"

# 先试 import，失败就打印具体错误
python -c "import main; print('OK')" 2>&1

echo "Starting uvicorn..."
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
