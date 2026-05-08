#!/bin/bash
set -e
cd "$(dirname "$0")"

# ── Environment ──
export PORT="${PORT:-8000}"

# ── Generate runtime files from env vars ──
mkdir -p gateway/agents/cbt/agent gateway/data gateway/workspace/cbt/memory gateway/workspace/cbt/state
if [ -n "$DEEPSEEK_API_KEY" ]; then
  # Gateway auth-profiles.json (agent 使用)
  cat > gateway/agents/cbt/agent/auth-profiles.json << AUTH_EOF
{
  "version": 1,
  "profiles": {
    "deepseek:default": {
      "type": "api_key",
      "provider": "deepseek",
      "key": "${DEEPSEEK_API_KEY}"
    }
  }
}
AUTH_EOF
  # Gateway .env（模板变量替换用）
  echo "DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}" > gateway/.env
  echo "[start] Gateway auth files generated"
else
  echo "[start] WARNING: DEEPSEEK_API_KEY not set, Gateway may fail"
fi

# ── Ensure Node modules are installed ──
if [ ! -f "node_modules/openclaw/dist/index.js" ]; then
  echo "[start] Installing OpenClaw Gateway..."
  npm install openclaw@latest || true
fi

# ── Start OpenClaw Gateway (background) ──
# Gateway 必须从 ~/.openclaw/ 读取配置（硬拷贝，不用软链接）
rm -rf "$HOME/.openclaw"
cp -r "$(pwd)/gateway" "$HOME/.openclaw"
export OPENCLAW_HOME="$HOME/.openclaw"

echo "[start] Config check:"
echo "  OPENCLAW_HOME=$OPENCLAW_HOME"
echo "  openclaw.json: $([ -f "$OPENCLAW_HOME/openclaw.json" ] && echo YES || echo NO)"
echo "  workspace/cbt: $([ -d "$OPENCLAW_HOME/workspace/cbt" ] && echo YES || echo NO)"
echo "[start] Launching OpenClaw Gateway..."
GATEWAY_PID=""
if command -v npx >/dev/null 2>&1; then
  npx openclaw gateway --port 18789 &
  GATEWAY_PID=$!
elif [ -f "node_modules/openclaw/dist/index.js" ]; then
  node node_modules/openclaw/dist/index.js gateway --port 18789 &
  GATEWAY_PID=$!
elif command -v openclaw >/dev/null 2>&1; then
  openclaw gateway --port 18789 &
  GATEWAY_PID=$!
fi
if [ -n "$GATEWAY_PID" ]; then
  echo "[start] Gateway PID=$GATEWAY_PID"
else
  echo "[start] WARNING: Could not start Gateway"
fi

# Wait for Gateway to be ready
if [ -n "$GATEWAY_PID" ]; then
  for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:18789/health > /dev/null 2>&1; then
      echo "[start] Gateway ready (port 18789)"
      break
    fi
    if [ $i -eq 30 ]; then
      echo "[start] WARNING: Gateway not ready after 30s, continuing anyway"
    fi
    sleep 1
  done
fi

# ── Find Python ──
PY=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY="$cmd"
        break
    fi
done

# Fallback: search nix store for Python
if [ -z "$PY" ]; then
  for d in /nix/store/*python*3.1*/bin /nix/store/*python3*/bin; do
    if [ -x "$d/python3" ]; then
      export PATH="$d:$PATH"
      PY="python3"
      echo "[start] Found Python in nix store: $d"
      break
    fi
  done 2>/dev/null
fi

if [ -z "$PY" ]; then
    echo "ERROR: No Python found!"
    echo "PATH=$PATH"
    ls /usr/bin/python* 2>/dev/null || true
    ls /usr/local/bin/python* 2>/dev/null || true
    ls /nix/store/*python3*/bin/python* 2>/dev/null | head -5 || true
    exit 1
fi

echo "=== XiaoNuan CBT ==="
echo "Python=$PY  PORT=$PORT  Gateway=18789"

exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
