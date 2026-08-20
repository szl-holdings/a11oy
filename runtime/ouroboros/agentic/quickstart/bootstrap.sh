#!/usr/bin/env bash
# © 2026 Lutar, Stephen P. — SZL Holdings · Apache-2.0
# bootstrap.sh — one-line setup for the SZL agentic workstation.
# Prefers Bun, falls back to Node. Parallel install. Cold-start target: ≤ 30s.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PAYLOAD_ROOT="$(cd "$ROOT/.." && pwd)"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  SZL Holdings — Agentic Bootstrap                             ║"
echo "║  Operator: Lutar, Stephen P. · ORCID 0009-0001-0110-4173      ║"
echo "║  Doctrine: V6                                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# 1. Pick runtime
if command -v bun >/dev/null 2>&1; then
  RUN="bun"
  echo "[bootstrap] using Bun ($(bun --version))"
elif command -v node >/dev/null 2>&1; then
  RUN="node"
  echo "[bootstrap] using Node ($(node --version))"
else
  echo "[bootstrap] FAIL: neither Bun nor Node found"
  exit 1
fi

# 2. Doctrine preflight first
echo "[bootstrap] running doctrine preflight..."
bash "$PAYLOAD_ROOT/02_doctrine/preflight.sh" "$PAYLOAD_ROOT" >/tmp/preflight.log 2>&1 || {
  echo "[bootstrap] preflight FAILED — see /tmp/preflight.log"
  tail -20 /tmp/preflight.log
  exit 1
}
echo "[bootstrap] preflight PASS"

# 3. Install deps (parallel)
cd "$ROOT"
if [ "$RUN" = "bun" ]; then
  bun install --silent &
else
  if command -v pnpm >/dev/null 2>&1; then pnpm install --silent &
  else npm install --silent & fi
fi
INSTALL_PID=$!

# 4. While deps install, check secrets
echo "[bootstrap] checking secrets..."
[ -z "${ANTHROPIC_API_KEY:-}" ] && echo "[bootstrap] WARN: ANTHROPIC_API_KEY not set — a11oy will fall back to stub" || echo "[bootstrap] ANTHROPIC_API_KEY: present"
[ -z "${OPENAI_API_KEY:-}"    ] && echo "[bootstrap] WARN: OPENAI_API_KEY not set — provider race disabled"              || echo "[bootstrap] OPENAI_API_KEY: present"

wait $INSTALL_PID
echo "[bootstrap] deps installed"

# 5. Start MCP server
MCP_PORT="${MCP_PORT:-8090}"
A11OY_PORT="${A11OY_PORT:-8091}"

if [ "$RUN" = "bun" ]; then
  (cd "$ROOT" && bun run mcp-server/src/index.ts > /tmp/mcp.log 2>&1 &)
else
  (cd "$ROOT" && npx -y tsx mcp-server/src/index.ts > /tmp/mcp.log 2>&1 &)
fi

# 6. Wait for healthz (up to 10s)
echo -n "[bootstrap] waiting for MCP server..."
for i in $(seq 1 20); do
  if curl -sf "http://localhost:${MCP_PORT}/healthz" >/dev/null 2>&1; then
    echo " up"
    break
  fi
  echo -n "."
  sleep 0.5
done

# 7. Summary
echo ""
echo "──────────────────────────────────────────────────────────────"
echo "  MCP server:    http://localhost:${MCP_PORT}/healthz"
echo "  Tools list:    http://localhost:${MCP_PORT}/tools"
echo "  Logs:          /tmp/mcp.log"
echo ""
echo "  Cursor:        opens .cursorrules + cursor.json automatically"
echo "  Claude Code:   reads agents/claude/CLAUDE.md on launch"
echo "  Replit Agent:  reads agents/replit/replit-agent.md per session"
echo "──────────────────────────────────────────────────────────────"
echo ""
echo "Try it:"
echo "  curl -s http://localhost:${MCP_PORT}/tools | jq '.tools | length'"
echo "  curl -s -X POST http://localhost:${MCP_PORT}/call/bekenstein_bound \\"
echo "    -H 'content-type: application/json' \\"
echo "    -d '{\"radius_m\":1,\"energy_j\":1}' | jq"
echo ""
