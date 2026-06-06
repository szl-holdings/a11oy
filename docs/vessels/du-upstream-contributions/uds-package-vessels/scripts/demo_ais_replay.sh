#!/usr/bin/env bash
# demo_ais_replay.sh — Replay sample AIS data through vessels
#
# Purpose: Demonstrate dark-vessel detection and sanctions screening in
# UDS demo mode without a live AIS provider subscription.
#
# Prerequisites (run from cluster or via kubectl exec):
#   - vessels pod running in the vessels namespace
#   - AIS_REPLAY_MODE=true in pod environment
#
# Usage:
#   bash demo_ais_replay.sh [--verbose]
#
# What it does:
#   1. Emits 5 sample AIS position reports (NMEA-style JSON) via vessels API
#   2. One vessel has a 6-hour AIS gap → triggers dark-vessel detection
#   3. One vessel is flagged on OFAC SDN list (test MMSI) → triggers sanctions alert
#   4. Prints receipt hashes for each alert

set -euo pipefail

VESSELS_API="${VESSELS_API_URL:-http://localhost:8080}"
VERBOSE="${1:-}"

log() { echo "[demo_ais_replay] $*"; }

# Sample AIS position reports
# Fields: mmsi, lat, lng, speed_knots, heading, timestamp_iso, vessel_name
AIS_MESSAGES=(
  '{"mmsi":"123456789","lat":1.2897,"lng":103.8501,"speed":12.3,"heading":045,"ts":"2026-06-16T06:00:00Z","name":"MV TAMAR EXPRESS","flag":"PA"}'
  '{"mmsi":"234567890","lat":25.7617,"lng":55.9653,"speed":0.0,"heading":000,"ts":"2026-06-16T06:05:00Z","name":"MT AURORA PRINCE","flag":"LR"}'
  '{"mmsi":"345678901","lat":51.9106,"lng":4.4814,"speed":8.7,"heading":270,"ts":"2026-06-16T06:10:00Z","name":"MV ROTTERDAM SPIRIT","flag":"NL"}'
  # This vessel has a simulated 6-hour AIS gap (last seen 6h ago) → dark-vessel trigger
  '{"mmsi":"456789012","lat":35.6762,"lng":139.6503,"speed":0.0,"heading":000,"ts":"2026-06-16T06:15:00Z","name":"MT SILENT MERIDIAN","flag":"PA","ais_gap_hours":6}'
  # This vessel uses a test MMSI flagged in the demo sanctions list → OFAC hit trigger
  '{"mmsi":"999000001","lat":4.9031,"lng":114.9399,"speed":11.2,"heading":135,"ts":"2026-06-16T06:20:00Z","name":"MV SANCTIONED VESSEL TEST","flag":"KP"}'
)

log "Starting AIS replay — ${#AIS_MESSAGES[@]} position reports"
log "vessels API: $VESSELS_API"
log ""

RECEIPT_HASHES=()

for i in "${!AIS_MESSAGES[@]}"; do
  MSG="${AIS_MESSAGES[$i]}"
  MMSI=$(echo "$MSG" | grep -o '"mmsi":"[^"]*"' | cut -d'"' -f4)
  NAME=$(echo "$MSG" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

  log "[$((i+1))/${#AIS_MESSAGES[@]}] Ingesting: $NAME (MMSI: $MMSI)"

  if [[ "$VERBOSE" == "--verbose" ]]; then
    log "  Payload: $MSG"
  fi

  # POST to vessels AIS ingest endpoint
  # In Phase 2, this hits the real vessels API.
  # In demo mode, we simulate the response.
  RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$MSG" \
    "$VESSELS_API/api/vessels/ais/ingest" 2>/dev/null || echo '{"receipt_hash":"demo-'$i'-'$(date +%s)'","status":"demo_mode"}
200')

  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | head -1)

  if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "201" ]]; then
    RECEIPT=$(echo "$BODY" | grep -o '"receipt_hash":"[^"]*"' | cut -d'"' -f4 || echo "demo-receipt-$i")
    RECEIPT_HASHES+=("$RECEIPT")
    log "  ✓ Ingested — receipt: $RECEIPT"
  else
    # Demo mode fallback
    DEMO_RECEIPT="demo-$(echo $MMSI | md5sum | cut -c1-12)"
    RECEIPT_HASHES+=("$DEMO_RECEIPT")
    log "  ✓ Demo mode — simulated receipt: $DEMO_RECEIPT"
  fi
  sleep 0.5
done

log ""
log "=== AIS Replay Summary ==="
log "Vessels processed: ${#AIS_MESSAGES[@]}"
log ""
log "Expected detections:"
log "  • MT SILENT MERIDIAN (MMSI 456789012) — dark-vessel alert (6h AIS gap)"
log "  • MV SANCTIONED VESSEL TEST (MMSI 999000001) — OFAC sanctions hit"
log ""
log "Receipt hashes emitted:"
for i in "${!RECEIPT_HASHES[@]}"; do
  log "  [$((i+1))] ${RECEIPT_HASHES[$i]}"
done
log ""
log "Run verify_receipts.sh to confirm DSSE chain integrity."
log "Alerts visible at: $VESSELS_API/vessels/dark — Dark Vessel Detection"
log "Sanctions visible at: $VESSELS_API/vessels/sanctions — Sanctions Screening"
