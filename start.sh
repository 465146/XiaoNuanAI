#!/bin/bash
set -e
cd "$(dirname "$0")"

# ── Environment ──
export OPENCLAW_HOME="$(pwd)/gateway"
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

# ── Start OpenClaw Gateway (background) ──
# Gateway 默认从 ~/.openclaw/ 读取配置，创建软链接
GATEWAY_HOME="$HOME/.openclaw"
if [ ! -L "$GATEWAY_HOME" ] && [ ! -e "$GATEWAY_HOME" ]; then
  ln -sf "$(pwd)/gateway" "$GATEWAY_HOME"
  echo "[start] Linked gateway -> ~/.openclaw"
fi
export OPENCLAW_HOME="$(pwd)/gateway"

echo "[start] Config check:"
echo "  OPENCLAW_HOME=$OPENCLAW_HOME"
echo "  config exists: $([ -f "$OPENCLAW_HOME/openclaw.json" ] && echo YES || echo NO)"
echo "  symlink: $([ -L "$HOME/.openclaw" ] && echo '->' "$(readlink "$HOME/.openclaw")" || echo none)"
echo "[start] Launching OpenClaw Gateway..."
node node_modules/openclaw/dist/index.js gateway --port 18789 &
GATEWAY_PID=$!
echo "[start] Gateway PID=$GATEWAY_PID"

# Wait for Gateway to be ready
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

# ── Find Python ──
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
echo "Python=$PY  PORT=$PORT  Gateway=18789"

exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
