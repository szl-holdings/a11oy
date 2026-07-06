#!/usr/bin/env bash
# install-a11oy-autodeploy.sh — one-shot installer (run ONCE on the Hetzner box).
# Sets up automatic a-11-oy.com redeploy: a small systemd timer polls GitHub main
# every 3 minutes and runs `a11oy-rebuild` only when origin/main has actually
# moved. Idempotent: safe to re-run; it just rewrites the unit files.
#
# WHY A POLLER (not a GitHub webhook): the box has no public inbound endpoint
# wired for CI, and polling origin/main is cheap (one `git ls-remote`). When you
# later expose a webhook, swap the timer for a webhook receiver — the rebuild
# command is identical.
#
# USAGE (on the box, as root or via sudo):
#   curl -fsSL <raw a11oy repo>/ops/install-a11oy-autodeploy.sh | sudo bash
#   # or: scp this file over and `sudo bash install-a11oy-autodeploy.sh`
#
# UNINSTALL:
#   sudo systemctl disable --now a11oy-autodeploy.timer && \
#   sudo rm -f /etc/systemd/system/a11oy-autodeploy.{service,timer} /usr/local/bin/a11oy-autodeploy-check
set -euo pipefail

REPO_DIR="${A11OY_REPO_DIR:-/opt/szl/a11oy}"
BRANCH="${A11OY_BRANCH:-main}"
REBUILD_BIN="${A11OY_REBUILD_BIN:-/usr/local/bin/a11oy-rebuild}"
STATE_FILE="/var/lib/a11oy-autodeploy/last_deployed_sha"

echo "[autodeploy] repo=$REPO_DIR branch=$BRANCH rebuild=$REBUILD_BIN"
[ -x "$REBUILD_BIN" ] || { echo "ERROR: $REBUILD_BIN not found/executable. Install a11oy-rebuild first."; exit 1; }
mkdir -p "$(dirname "$STATE_FILE")"

# --- the check script: rebuild only when origin/main moved -------------------
cat > /usr/local/bin/a11oy-autodeploy-check <<EOF
#!/usr/bin/env bash
set -uo pipefail
REPO_DIR="$REPO_DIR"; BRANCH="$BRANCH"; REBUILD_BIN="$REBUILD_BIN"; STATE_FILE="$STATE_FILE"
cd "\$REPO_DIR" || exit 0
REMOTE_SHA=\$(git ls-remote origin "refs/heads/\$BRANCH" 2>/dev/null | awk '{print \$1}')
[ -z "\$REMOTE_SHA" ] && { echo "[autodeploy] cannot reach origin; skip"; exit 0; }
LAST=\$(cat "\$STATE_FILE" 2>/dev/null || echo "")
if [ "\$REMOTE_SHA" = "\$LAST" ]; then exit 0; fi
echo "[autodeploy] origin/\$BRANCH moved \$LAST -> \$REMOTE_SHA ; rebuilding a-11-oy.com"
if "\$REBUILD_BIN"; then echo "\$REMOTE_SHA" > "\$STATE_FILE"; echo "[autodeploy] OK, deployed \$REMOTE_SHA"
else echo "[autodeploy] a11oy-rebuild FAILED for \$REMOTE_SHA (will retry next tick)"; exit 1; fi
EOF
chmod +x /usr/local/bin/a11oy-autodeploy-check

# --- systemd service + timer (every 3 min) -----------------------------------
cat > /etc/systemd/system/a11oy-autodeploy.service <<'EOF'
[Unit]
Description=a-11-oy.com auto-deploy (rebuild when GitHub main moves)
After=network-online.target docker.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/a11oy-autodeploy-check
EOF

cat > /etc/systemd/system/a11oy-autodeploy.timer <<'EOF'
[Unit]
Description=Poll GitHub main every 3 min and redeploy a-11-oy.com on change
[Timer]
OnBootSec=2min
OnUnitActiveSec=3min
AccuracySec=30s
Persistent=true
[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now a11oy-autodeploy.timer
echo "[autodeploy] installed + enabled. Status:"
systemctl status a11oy-autodeploy.timer --no-pager | head -8 || true
echo "[autodeploy] next runs:"; systemctl list-timers a11oy-autodeploy.timer --no-pager | head -3 || true
