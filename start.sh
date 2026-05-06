#!/bin/bash
# 小暖 CBT 启动脚本 (Linux / Railway)
set -e

echo "=== XiaoNuan CBT Starting ==="

# ── OpenClaw Gateway（可选）──
# Railway 上 openclaw 可能无法正常工作（微信插件依赖本地环境）
# 尝试启动，失败不影响网站功能
if command -v openclaw &> /dev/null || command -v npx &> /dev/null; then
    echo "[openclaw] Starting Gateway (best-effort)..."
    openclaw gateway --port 18789 &>/tmp/openclaw.log &
    sleep 3
    if curl -s http://127.0.0.1:18789/health >/dev/null 2>&1; then
        echo "[openclaw] Gateway ready"
    else
        echo "[openclaw] Gateway failed to start — website will run without enhanced mode"
    fi
else
    echo "[openclaw] Not available — running in basic mode"
fi

# ── FastAPI 网站 ──
echo "[web] Starting FastAPI on port ${PORT:-8000}..."
cd "$(dirname "$0")"
exec uv run uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
