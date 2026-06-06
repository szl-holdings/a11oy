#!/usr/bin/env bash
# scripts/preflight.sh — SZL Demo Cluster Preflight Check
# Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1
# Exit 0 = all checks passed. Exit 1 = blocking issue found.
#
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass()  { echo -e "  ${GREEN}✅  PASS${NC}  $*"; PASS_COUNT=$((PASS_COUNT+1)); }
fail()  { echo -e "  ${RED}⛔  FAIL${NC}  $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }
warn()  { echo -e "  ${YELLOW}⚠️   WARN${NC}  $*"; WARN_COUNT=$((WARN_COUNT+1)); }

echo ""
echo -e "${YELLOW}=== SZL Demo Cluster — Preflight Check ===${NC}"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# ─────────────────────────────────────────────────────────
# 1. Docker running
# ─────────────────────────────────────────────────────────
echo "1. Docker"
if docker info >/dev/null 2>&1; then
  DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
  pass "Docker daemon running — version $DOCKER_VERSION"
  # Check minimum version (24.0)
  DOCKER_MAJOR=$(echo "$DOCKER_VERSION" | cut -d'.' -f1)
  if [ "${DOCKER_MAJOR}" -ge 24 ] 2>/dev/null; then
    pass "Docker version ≥ 24.0"
  else
    warn "Docker version < 24.0 (have $DOCKER_VERSION). Upgrade recommended."
  fi
else
  fail "Docker daemon NOT running. Start Docker Desktop or: sudo systemctl start docker"
fi

# ─────────────────────────────────────────────────────────
# 2. k3d version
# ─────────────────────────────────────────────────────────
echo ""
echo "2. k3d"
REQUIRED_K3D_MAJOR=5
REQUIRED_K3D_MINOR=8
if command -v k3d >/dev/null 2>&1; then
  K3D_VERSION=$(k3d version --short 2>/dev/null | grep -oP 'v[\d.]+' | head -1 || echo "unknown")
  K3D_MAJOR=$(echo "$K3D_VERSION" | grep -oP '[\d]+' | head -1 || echo "0")
  K3D_MINOR=$(echo "$K3D_VERSION" | grep -oP '[\d]+' | sed -n '2p' || echo "0")
  pass "k3d found — $K3D_VERSION"
  if [ "${K3D_MAJOR}" -ge "${REQUIRED_K3D_MAJOR}" ] && \
     [ "${K3D_MINOR}" -ge "${REQUIRED_K3D_MINOR}" ] 2>/dev/null; then
    pass "k3d version ≥ v${REQUIRED_K3D_MAJOR}.${REQUIRED_K3D_MINOR}.x"
  else
    warn "k3d version $K3D_VERSION may be too old. Need v${REQUIRED_K3D_MAJOR}.${REQUIRED_K3D_MINOR}+. Install: mise use k3d@5.8.3"
  fi
else
  fail "k3d not found. Install: mise use k3d@5.8.3  OR  brew install k3d"
fi

# ─────────────────────────────────────────────────────────
# 3. kubectl
# ─────────────────────────────────────────────────────────
echo ""
echo "3. kubectl"
if command -v kubectl >/dev/null 2>&1; then
  KCL_VERSION=$(kubectl version --client --short 2>/dev/null | grep -oP 'v[\d.]+' || echo "unknown")
  pass "kubectl found — $KCL_VERSION"
else
  fail "kubectl not found. Install: mise use kubectl@1.30"
fi

# ─────────────────────────────────────────────────────────
# 4. uds CLI
# ─────────────────────────────────────────────────────────
echo ""
echo "4. uds CLI"
if command -v uds >/dev/null 2>&1; then
  UDS_VER=$(uds version 2>/dev/null || echo "unknown")
  pass "uds CLI found — $UDS_VER"
else
  fail "uds CLI not found. Install (raw binary, not a tarball): curl -fSL https://github.com/defenseunicorns/uds-cli/releases/download/v0.32.0/uds-cli_v0.32.0_Linux_amd64 -o /usr/local/bin/uds && chmod +x /usr/local/bin/uds"
fi

# ─────────────────────────────────────────────────────────
# 5. Ports free (80, 443, 6550)
# ─────────────────────────────────────────────────────────
echo ""
echo "5. Port availability (80, 443, 6550)"
for port in 80 443 6550; do
  if lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1 || \
     ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    fail "Port ${port} is in use. Find and stop the process: lsof -i :${port}"
  else
    pass "Port ${port} is free"
  fi
done

# ─────────────────────────────────────────────────────────
# 6. No leftover szl-demo containers
# ─────────────────────────────────────────────────────────
echo ""
echo "6. Leftover containers / clusters"
if k3d cluster list 2>/dev/null | grep -q "szl-demo"; then
  warn "k3d cluster 'szl-demo' already exists. Run: make demo-tear-down  to remove it first."
else
  pass "No leftover 'szl-demo' cluster found"
fi

LEFTOVER=$(docker ps -a --filter "name=k3d-szl-demo" --format "{{.Names}}" 2>/dev/null || true)
if [ -n "$LEFTOVER" ]; then
  warn "Leftover k3d containers found: $LEFTOVER  — run: make demo-tear-down"
else
  pass "No leftover k3d containers"
fi

# ─────────────────────────────────────────────────────────
# 7. inotify limits
# ─────────────────────────────────────────────────────────
echo ""
echo "7. inotify limits"
WATCHES=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null || echo "0")
INSTANCES=$(cat /proc/sys/fs/inotify/max_user_instances 2>/dev/null || echo "0")
if [ "${WATCHES}" -ge 1048576 ] 2>/dev/null; then
  pass "inotify max_user_watches = ${WATCHES} (≥ 1048576)"
else
  warn "inotify max_user_watches = ${WATCHES} (need ≥ 1048576). Fix: sudo sysctl fs.inotify.max_user_watches=1048576"
fi
if [ "${INSTANCES}" -ge 1024 ] 2>/dev/null; then
  pass "inotify max_user_instances = ${INSTANCES} (≥ 1024)"
else
  warn "inotify max_user_instances = ${INSTANCES} (need ≥ 1024). Fix: sudo sysctl fs.inotify.max_user_instances=8192"
fi

# ─────────────────────────────────────────────────────────
# 8. Available RAM
# ─────────────────────────────────────────────────────────
echo ""
echo "8. System resources"
if command -v free >/dev/null 2>&1; then
  TOTAL_RAM_KB=$(free | awk '/^Mem:/{print $2}')
  TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1024 / 1024 ))
  if [ "${TOTAL_RAM_GB}" -ge 14 ] 2>/dev/null; then
    pass "RAM: ${TOTAL_RAM_GB} GB (≥ 14 GB)"
  elif [ "${TOTAL_RAM_GB}" -ge 8 ] 2>/dev/null; then
    warn "RAM: ${TOTAL_RAM_GB} GB (recommend ≥ 16 GB; 8 GB minimum will be tight)"
  else
    fail "RAM: ${TOTAL_RAM_GB} GB — insufficient. Need ≥ 8 GB (recommend 16 GB)"
  fi
fi

# Disk free check
DISK_FREE_KB=$(df -k . 2>/dev/null | awk 'NR==2{print $4}' || echo "0")
DISK_FREE_GB=$(( DISK_FREE_KB / 1024 / 1024 ))
if [ "${DISK_FREE_GB}" -ge 28 ] 2>/dev/null; then
  pass "Disk free: ${DISK_FREE_GB} GB (≥ 30 GB)"
elif [ "${DISK_FREE_GB}" -ge 20 ] 2>/dev/null; then
  warn "Disk free: ${DISK_FREE_GB} GB (recommend ≥ 30 GB; 20 GB will work but is tight)"
else
  fail "Disk free: ${DISK_FREE_GB} GB — insufficient. Need ≥ 20 GB (recommend 30 GB+)"
fi

# ─────────────────────────────────────────────────────────
# 9. Network reachability (GHCR and HF)
# ─────────────────────────────────────────────────────────
echo ""
echo "9. Network reachability"
for url in \
  "https://ghcr.io" \
  "https://szlholdings-amaru.hf.space/api/health" \
  "https://szlholdings-sentra.hf.space/api/health"; do
  code=$(curl -sf --max-time 5 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "ERR")
  if [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ]; then
    pass "Reachable: $url ($code)"
  else
    warn "Not reachable: $url ($code) — airgap or network issue"
  fi
done

# ─────────────────────────────────────────────────────────
# 10. python3 (for seed-receipts)
# ─────────────────────────────────────────────────────────
echo ""
echo "10. Python 3"
if command -v python3 >/dev/null 2>&1; then
  PY_VER=$(python3 --version 2>&1)
  pass "python3 found — $PY_VER"
else
  warn "python3 not found — seed-receipts.py will not run"
fi

# ─────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────"
echo "  PASS: ${PASS_COUNT}   WARN: ${WARN_COUNT}   FAIL: ${FAIL_COUNT}"
echo "─────────────────────────────────────────"

if [ "${FAIL_COUNT}" -gt 0 ]; then
  echo -e "${RED}⛔  PREFLIGHT FAILED — fix the items above before running demo-up${NC}"
  exit 1
elif [ "${WARN_COUNT}" -gt 0 ]; then
  echo -e "${YELLOW}⚠️   PREFLIGHT PASSED WITH WARNINGS — demo may still work${NC}"
  exit 0
else
  echo -e "${GREEN}✅  PREFLIGHT PASSED — TOWER IS DEMO-READY${NC}"
  exit 0
fi
