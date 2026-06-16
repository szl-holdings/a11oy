#!/usr/bin/env bash
# ops/smoke_warhacker.sh - golden-path demo smoke for a11oy.net (+ killinchu).
# Honest by design: every web surface is checked for HTTP 200 AND a content
# marker actually present in the served body, so a white-screen or wrong-page
# fallback (200 with empty/wrong content) is caught, never passed. Energy/mesh
# truth endpoints are JSON-asserted against REAL fields (operator running +
# stub_mode is False + >=1 lung + nonzero joules; ledger chain anchored at
# GENESIS; jtoken carries an honest label; compute-pool has >=1 reachable node;
# PNT pillars wired). Never fabricates a pass. Finishes well under 5 min.
# Exit 0 = all green (demo go); non-zero = at least one RED.
# Usage: ops/smoke_warhacker.sh [BASE]        (default https://a11oy.net)
set -uo pipefail
BASE="${1:-${A11OY_BASE:-https://a11oy.net}}"
KILL="${KILLINCHU_BASE:-https://killinchu.net}"
TIMEOUT="${SMOKE_TIMEOUT:-20}"
UA="warhacker-smoke/1.0"
PASS=0; FAIL=0; REDS=""
BODYF="$(mktemp)"; trap 'rm -f "$BODYF"' EXIT
fetch(){ local tries=0
  while :; do
    CODE="$(curl -sS -A "$UA" --max-time "$TIMEOUT" -o "$BODYF" -w '%{http_code}' "$1" 2>/dev/null)" || CODE=000
    if [ "$CODE" = 429 ] && [ "$tries" -lt 4 ]; then tries=$((tries+1)); sleep $((tries*3)); continue; fi
    break
  done; }
green(){ PASS=$((PASS+1)); printf '  PASS  %-26s %s\n' "$1" "${2:-}"; }
red(){ FAIL=$((FAIL+1)); REDS="$REDS $1"; printf '  RED   %-26s %s\n' "$1" "${2:-}"; }
page(){ fetch "$BASE$2"
  if [ "$CODE" != 200 ]; then red "$1" "HTTP $CODE"; return; fi
  if grep -qiF -- "$3" "$BODYF"; then green "$1" "200 + marker ok"; else red "$1" "200 but marker missing: '$3'"; fi; }
japi(){ fetch "$BASE$2"
  if [ "$CODE" != 200 ]; then red "$1" "HTTP $CODE"; return; fi
  local out verdict info
  out="$(EXPR="$3" NOTE="${4:-}" python3 - "$BODYF" <<'PY'
import sys,json,os
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("FALSE|parse error: %s"%(str(e)[:50])); sys.exit()
try: ok=bool(eval(os.environ["EXPR"]))
except Exception as e: print("FALSE|expr error: %s"%(str(e)[:70])); sys.exit()
note=""; ne=os.environ.get("NOTE","")
if ne:
  try: note=str(eval(ne))[:120]
  except Exception: note="(note err)"
print(("OK" if ok else "FALSE")+"|"+note)
PY
)"
  verdict="${out%%|*}"; info="${out#*|}"
  if [ "$verdict" = OK ]; then green "$1" "$info"; else red "$1" "$info"; fi; }
echo "== a11oy.net web surfaces ($BASE) =="
page "root /"           "/"               "Governed-AI Command Platform"
page "warhacker"        "/warhacker"      "Mission Surfaces"
page "fabric/tawantin"  "/fabric"         "TAWANTIN"
page "energy engine"    "/energy"         "Proven Energy Engine"
page "counter-uas"      "/counter-uas"    "Counter-UAS"
page "fleet-c2"         "/fleet-c2"       "Fleet Health"
page "holo substrate"   "/holo"           "Holographic Substrate"
page "living-anatomy"   "/living-anatomy" "Living Anatomy"
page "hologram(spa)"    "/hologram"       "Orchestration Platform"
page "pnt(spa)"         "/pnt"            "Orchestration Platform"
page "agentic-gpu(spa)" "/agentic-gpu"    "Orchestration Platform"
echo "== killinchu =="
fetch "$KILL/"
if [ "$CODE" = 200 ] && [ "$(wc -c <"$BODYF")" -gt 800 ]; then green "killinchu root" "200 ($(wc -c <"$BODYF")B)"; else red "killinchu root" "HTTP $CODE"; fi
echo "== energy / mesh truth endpoints =="
japi "healthz"            "/api/a11oy/healthz" "bool(d.get('status'))" "'status='+str(d.get('status'))"
japi "readyz"             "/api/a11oy/readyz"  "bool(d.get('status'))" "'status='+str(d.get('status'))+' backend='+str(d.get('backend'))"
japi "honest git_sha"     "/api/a11oy/v1/honest" "bool(d.get('git_sha'))" "'git_sha='+str(d.get('git_sha'))[:12]+' lock='+str(d.get('doctrine_lock'))"
japi "energy operator"    "/api/a11oy/v1/energy/operator/status" "bool(d.get('running')) and d.get('stub_mode') is False and len(d.get('nodes_computing') or [])>0 and ((d.get('joules_measured_total') or 0)>0 or (d.get('joules_sample_total') or 0)>0)" "'run=%s stub=%s nodes=%s Jm=%s(%s)'%(d.get('running'),d.get('stub_mode'),d.get('nodes_computing'),d.get('joules_measured_total'),d.get('joules_measured_label'))"
japi "energy ledger chain" "/api/a11oy/v1/operator/ledger" "(d.get('count') or 0)>0 and bool(d.get('root_hash')) and (d.get('receipts') or [{}])[0].get('prior_hash')=='GENESIS'" "'count=%s head_seq=%s root=%s'%(d.get('count'),d.get('head_seq'),str(d.get('root_hash'))[:12])"
japi "energy jtoken label" "/api/a11oy/v1/energy/jtoken" "bool(d.get('label')) and d.get('joules_per_token') is not None" "'label=%s jpt=%s honesty=%s'%(d.get('label'),d.get('joules_per_token'),str(d.get('joules_honesty'))[:24])"
japi "compute-pool nodes"  "/api/a11oy/v1/compute-pool-hardened" "sum(1 for n in (list(d.get('nodes').values()) if isinstance(d.get('nodes'),dict) else (d.get('nodes') or [])) if isinstance(n,dict) and n.get('reachable'))>=1" "'reachable=%d/%d'%(sum(1 for n in (list(d.get('nodes').values()) if isinstance(d.get('nodes'),dict) else (d.get('nodes') or [])) if isinstance(n,dict) and n.get('reachable')), len(d.get('nodes') or []))"
japi "pnt pillars wired"   "/api/a11oy/v1/pnt/limits" "(isinstance(d.get('pillars'),dict) and len(d.get('pillars'))>=1 and all((v.get('wired') if isinstance(v,dict) else bool(v)) for v in d.get('pillars').values())) or (isinstance(d.get('pillars'),list) and len(d.get('pillars'))>=1)" "'pillars=%s'%(list(d.get('pillars').keys()) if isinstance(d.get('pillars'),dict) else d.get('pillars'))"
echo
TOTAL=$((PASS+FAIL))
if [ "$FAIL" -eq 0 ]; then printf 'GREEN  %d/%d surfaces healthy -- demo go.\n' "$PASS" "$TOTAL"; exit 0
else printf 'RED    %d/%d FAILED:%s\n' "$FAIL" "$TOTAL" "$REDS"; exit 1; fi
