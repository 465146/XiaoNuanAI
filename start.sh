#!/bin/bash
cd "$(dirname "$0")"

# 找到可用的 Python
PY=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY="$cmd"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "ERROR: No Python found!"
    echo "PATH=$PATH"
    ls /usr/bin/python* 2>/dev/null || true
    ls /usr/local/bin/python* 2>/dev/null || true
    exit 1
fi

echo "=== XiaoNuan CBT ==="
echo "Python=$PY  PORT=${PORT:-8000}"

exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
