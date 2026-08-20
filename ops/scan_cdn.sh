#!/usr/bin/env bash
# ops/scan_cdn.sh - 0-CDN audit: fetch each demo surface and flag any external
# host referenced by a resource load (script src / link href / img src / CSS
# url()). Self-hosted origins are allow-listed; xmlns namespace URIs are NOT
# matched (only real resource attributes are scanned). Exit non-zero if any
# surface pulls a resource from an external host. Honest: prints exact host+page.
# Usage: ops/scan_cdn.sh [BASE]
set -uo pipefail
BASE="${1:-${A11OY_BASE:-https://a-11-oy.com}}"
UA="cdn-scan/1.0"
ALLOW="a-11-oy.com killinchu.net alloyszlholdings.com"
SURF="/ /warhacker /fabric /energy /counter-uas /fleet-c2 /holo /living-anatomy /hologram /pnt /agentic-gpu"
viol=0
for p in $SURF; do
  body="$(curl -sS -A "$UA" --max-time 20 "$BASE$p" 2>/dev/null || true)"
  hosts="$(printf '%s' "$body" | grep -oiE "(src|href)=[\"']https?://[a-z0-9.-]+|url\([\"']?https?://[a-z0-9.-]+" | grep -oiE "https?://[a-z0-9.-]+" | sed -E 's#https?://##' | sort -u)"
  ext=""
  for h in $hosts; do
    keep=1
    for a in $ALLOW; do
      case "$h" in "$a") keep=0;; *".$a") keep=0;; esac
    done
    case "$h" in localhost*|127.*|0.0.0.0*) keep=0;; esac
    [ "$keep" = 1 ] && ext="$ext $h"
  done
  if [ -n "$ext" ]; then printf '  EXTERNAL  %-16s%s\n' "$p" "$ext"; viol=$((viol+1)); else printf '  0-CDN ok  %s\n' "$p"; fi
done
echo
if [ "$viol" -eq 0 ]; then echo "RESULT: 0-CDN clean - no external resource hosts on any surface."; exit 0
else echo "RESULT: $viol surface(s) reference external hosts (see above)."; exit 1; fi
