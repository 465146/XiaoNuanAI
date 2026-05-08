#!/bin/bash
set -e
cd "$(dirname "$0")"

export PORT="${PORT:-8000}"

# ── Install Node.js if not available ──
if ! command -v node >/dev/null 2>&1; then
  echo "[start] Node.js not found, downloading..."
  NODE_VER="22.14.0"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VER}/node-v${NODE_VER}-linux-x64.tar.xz" -o /tmp/node.tar.xz
  tar -xJf /tmp/node.tar.xz -C /tmp
  export PATH="/tmp/node-v${NODE_VER}-linux-x64/bin:$PATH"
  echo "[start] Node.js v${NODE_VER} installed"
fi
echo "[start] node=$(node --version)  npm=$(npm --version)"

# ── Install OpenClaw ──
echo "[start] Installing openclaw..."
npm install openclaw@2026.4.8

# ── Generate Gateway runtime files ──
mkdir -p gateway/agents/cbt/agent gateway/workspace/cbt/memory gateway/workspace/cbt/state
if [ -n "$DEEPSEEK_API_KEY" ]; then
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
  echo "DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}" > gateway/.env
  echo "[start] Gateway auth files generated"
fi

# ── Start OpenClaw Gateway ──
rm -rf "$HOME/.openclaw"
cp -r "$(pwd)/gateway" "$HOME/.openclaw"
export OPENCLAW_HOME="$HOME/.openclaw"
echo "[start] Config: OPENCLAW_HOME=$OPENCLAW_HOME"
echo "[start] openclaw.json: $([ -f "$OPENCLAW_HOME/openclaw.json" ] && echo YES || echo NO)"

echo "[start] Launching OpenClaw Gateway..."
node node_modules/openclaw/dist/index.js gateway --port 18789 &
GATEWAY_PID=$!
echo "[start] Gateway PID=$GATEWAY_PID"

for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:18789/health > /dev/null 2>&1; then
    echo "[start] Gateway ready (port 18789)"
    break
  fi
  [ $i -eq 30 ] && echo "[start] WARNING: Gateway not ready after 30s"
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

# nix store fallback (for when provider installs but PATH misses it)
if [ -z "$PY" ]; then
  for d in /nix/store/*python*3.1*/bin; do
    if [ -x "$d/python3" ]; then
      export PATH="$d:$PATH"
      PY="python3"
      echo "[start] Found Python in nix store"
      break
    fi
  done 2>/dev/null
fi

if [ -z "$PY" ]; then
    echo "ERROR: No Python found!"
    echo "PATH=$PATH"
    ls -d /nix/store/*python3* 2>/dev/null | head -5 || echo "(none)"
    exit 1
fi

echo "=== XiaoNuan CBT ==="
echo "Python=$PY  PORT=$PORT  Gateway=18789"
exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
