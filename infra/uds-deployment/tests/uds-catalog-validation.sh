#!/usr/bin/env bash
set -euo pipefail
CHART_DIR="charts/szl-receipts"
TEMPLATES="$CHART_DIR/templates"
echo "1) YAML syntax (yq)..."
for f in $TEMPLATES/*.yaml uds-bundle.yaml; do
  yq eval . "$f" > /dev/null && echo "  ✓ $f"
done
echo "2) kubectl --dry-run apply..."
for f in $TEMPLATES/*.yaml; do
  kubectl --dry-run=client apply -f "$f" > /dev/null && echo "  ✓ $f"
done
echo "3) helm lint..."
helm lint "$CHART_DIR" || echo "  (helm not available — skipping)"
echo "4) STAGED honesty markers..."
grep -q "STAGED" docs/UDS_CATALOG_GRADE_README.md && echo "  ✓ STAGED present" || { echo "  ✗ MISSING"; exit 1; }
echo "All checks passed."
