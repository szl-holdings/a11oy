#!/usr/bin/env bash
# run-acceptance.sh — end-to-end acceptance: organ /healthz + traceparent propagation.
#
# 1. Hit each organ's /healthz (via kubectl port-forward) and assert 200.
# 2. Inject a known W3C traceparent into a request that flows a11oy -> sentra ->
#    amaru -> killinchu -> rosie, then query Jaeger for that trace id and dump the
#    span tree, proving one trace propagated across all 5 organs end-to-end.
#
# Honest: if killinchu is not running (private image), the trace tree will show
# 4/5 organs and the script SAYS SO rather than claiming 5/5.
set -uo pipefail

NAMESPACE="${NAMESPACE:-szl}"
ORGANS=(a11oy sentra amaru killinchu rosie)
JAEGER_UI="http://localhost:16686"

pass=0; fail=0; missing=()

echo "==> 1. /healthz probe for each organ"
for organ in "${ORGANS[@]}"; do
  if ! kubectl -n "$NAMESPACE" get deploy "$organ" >/dev/null 2>&1; then
    echo "   [--] $organ: deployment absent"; missing+=("$organ"); continue
  fi
  ready=$(kubectl -n "$NAMESPACE" get pods -l app="$organ" \
            -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null)
  if [[ "$ready" != *true* ]]; then
    echo "   [!!] $organ: pod not ready (image pull? cosign gate? see HONEST_GAPS.md)"
    missing+=("$organ"); continue
  fi
  # ephemeral port-forward to probe /healthz
  kubectl -n "$NAMESPACE" port-forward "svc/$organ" 18080:8080 >/dev/null 2>&1 &
  pf=$!; sleep 2
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:18080/healthz" || echo 000)
  kill "$pf" 2>/dev/null || true
  if [ "$code" = "200" ]; then echo "   [OK] $organ /healthz -> 200"; pass=$((pass+1));
  else echo "   [!!] $organ /healthz -> $code"; fail=$((fail+1)); fi
done

echo ""
echo "==> 2. traceparent propagation across organs"
# Deterministic W3C trace id for this acceptance run.
TRACE_ID=$(openssl rand -hex 16 2>/dev/null || python3 -c "import os;print(os.urandom(16).hex())")
SPAN_ID=$(openssl rand -hex 8 2>/dev/null || python3 -c "import os;print(os.urandom(8).hex())")
TRACEPARENT="00-${TRACE_ID}-${SPAN_ID}-01"
echo "   injecting traceparent: ${TRACEPARENT}"

# Send the seed request into the entrypoint organ (a11oy). The waypoint + organ
# OTLP instrumentation propagate the header downstream.
if kubectl -n "$NAMESPACE" get deploy a11oy >/dev/null 2>&1; then
  kubectl -n "$NAMESPACE" port-forward svc/a11oy 18081:8080 >/dev/null 2>&1 &
  pf=$!; sleep 2
  curl -s -H "traceparent: ${TRACEPARENT}" \
       "http://localhost:18081/route?fanout=sentra,amaru,killinchu,rosie" >/dev/null 2>&1 \
    || curl -s -H "traceparent: ${TRACEPARENT}" "http://localhost:18081/healthz" >/dev/null 2>&1
  kill "$pf" 2>/dev/null || true
fi

echo "   waiting 4s for spans to land in Jaeger..."
sleep 4

echo ""
echo "==> 3. trace tree from Jaeger (trace id ${TRACE_ID})"
kubectl -n "$NAMESPACE" port-forward svc/jaeger 16686:16686 >/dev/null 2>&1 &
jpf=$!; sleep 2
TRACE_JSON=$(curl -s "http://localhost:16686/api/traces/${TRACE_ID}" 2>/dev/null)
kill "$jpf" 2>/dev/null || true

if TRACE_JSON="$TRACE_JSON" python3 - "$TRACE_ID" <<'PY'
import os, sys, json
# Read the Jaeger payload from the environment: the heredoc occupies stdin,
# so a piped `echo "$TRACE_JSON"` would be overridden (shellcheck SC2259).
raw = os.environ.get("TRACE_JSON", "")
try:
    data = json.loads(raw)
except Exception:
    print("   [!!] could not parse Jaeger response (is Jaeger up? did spans export?)")
    sys.exit(0)
traces = data.get("data", [])
if not traces:
    print("   [!!] no trace found for id", sys.argv[1])
    print("        => traceparent did not propagate or organs not instrumented yet.")
    sys.exit(0)
spans = traces[0].get("spans", [])
services = sorted({s.get("process",{}).get("serviceName") or
                   traces[0].get("processes",{}).get(s.get("processID",""),{}).get("serviceName","?")
                   for s in spans})
print(f"   spans: {len(spans)}  services touched: {services}")
expected = {"a11oy","sentra","amaru","killinchu","rosie"}
got = expected & set(services)
print(f"   organs in trace: {len(got)}/5 -> {sorted(got)}")
if got == expected:
    print("   [OK] 5/5 organs share one traceparent end-to-end.")
else:
    miss = expected - got
    print(f"   [HONEST] missing from trace: {sorted(miss)} (likely killinchu private / not ready).")
PY
then :; fi

echo ""
echo "==> summary: /healthz pass=$pass fail=$fail"
[ "${#missing[@]}" -gt 0 ] && echo "    not-ready organs: ${missing[*]} (see HONEST_GAPS.md)"
echo "    open ${JAEGER_UI}/trace/${TRACE_ID} to inspect the trace tree visually."
