#!/bin/bash
cd "$(dirname "$0")"

echo "=== XiaoNuan CBT ==="
echo "PORT=${PORT:-8000}"

# 诊断（不阻塞启动）
python3 -c "import main; print('import ok')" 2>&1 || echo "import failed, trying uvicorn anyway..."

echo "Starting uvicorn..."
exec python3 -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
