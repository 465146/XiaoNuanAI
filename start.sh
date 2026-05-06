#!/bin/bash
# 小暖 CBT 启动脚本
# 1. 安装 OpenClaw（可选，如果 package.json 存在）
# 2. 启动 OpenClaw Gateway（可选，后台）
# 3. 安装 Python 依赖
# 4. 启动 FastAPI 网站

set -e

echo "=== 小暖 CBT 启动中 ==="

# ── OpenClaw Gateway（可选，如果已安装）──
if command -v openclaw &> /dev/null || [ -f "$HOME/.npm-global/bin/openclaw" ]; then
    echo "[openclaw] 启动 Gateway..."
    openclaw gateway --port 18789 &
    sleep 2
    echo "[openclaw] Gateway 已启动"
else
    echo "[openclaw] 未安装，跳过 Gateway（网站仍可正常使用）"
fi

# ── FastAPI 网站 ──
echo "[web] 启动 FastAPI..."
cd "$(dirname "$0")"
exec uv run uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
