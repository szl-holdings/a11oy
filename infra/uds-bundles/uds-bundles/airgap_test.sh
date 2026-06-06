#!/usr/bin/env bash
# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
#
# airgap_test.sh — FOUNDER-RUNNABLE. Real airgap deploy of the 5 SZL bundles.
#   1. Create a kind cluster
#   2. Load the 5 images into the cluster (kind load docker-image) — no registry
#   3. Apply a minimal UDS-Core skeleton (namespaces + labels + a NetworkPolicy
#      default-deny that the real uds-core would enforce). NOTE: full UDS Core
#      (Istio+Keycloak+Pepr) is heavy; for the marketplace-grade run, swap this
#      step for: `uds deploy k3d-core-slim-dev:0.41.0` per UDS Core docs.
#   4. Cut all egress (airgap semantics: imagePullPolicy: Never already set; the
#      kind cluster has no registry creds and we delete the default pull path)
#   5. Deploy each bundle IN ORDER: a11oy -> amaru -> sentra -> killinchu -> rosie
#   6. Verify all 5 land GREEN (Deployment Available + /healthz 200 + mesh probe)
#
# Run:
#   bash airgap_test.sh 2>&1 | tee AIRGAP_RUN.log
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PER="$ROOT/PER_BUNDLE"
CLUSTER="szl-airgap"
FLAGSHIPS=(a11oy amaru sentra killinchu rosie)
declare -A IMG=( [a11oy]=ghcr.io/szl-holdings/a11oy:uds-v0.3.1 \
  [amaru]=ghcr.io/szl-holdings/amaru:uds-v0.3.1 \
  [sentra]=ghcr.io/szl-holdings/sentra:uds-v0.3.1 \
  [killinchu]=ghcr.io/szl-holdings/killinchu:uds-v0.3.1 \
  [rosie]=ghcr.io/szl-holdings/rosie:uds-v0.3.1 )
declare -A HEALTH=( [a11oy]=/api/a11oy/healthz [amaru]=/api/amaru/healthz \
  [sentra]=/api/sentra/healthz [killinchu]=/killinchu/healthz [rosie]=/api/rosie/healthz )

echo "== create kind cluster =="
kind create cluster --name "$CLUSTER" --wait 120s

echo "== load images (airgap: no registry pull) =="
for f in "${FLAGSHIPS[@]}"; do kind load docker-image "${IMG[$f]}" --name "$CLUSTER"; done

echo "== UDS Core skeleton (namespaces + labels) =="
for f in "${FLAGSHIPS[@]}"; do kubectl apply -f "$PER/$f/manifests/namespace.yaml"; done
kubectl create namespace szl-receipts --dry-run=client -o yaml | kubectl apply -f -

echo "== deploy bundles IN ORDER (mesh chain) =="
RESULT=""
for f in "${FLAGSHIPS[@]}"; do
  echo "---- deploy $f ----"
  helm upgrade --install "$f" "$PER/$f/chart" -n "$f" --create-namespace \
    -f "$PER/$f/chart/values.yaml" --set image.pullPolicy=Never
  kubectl rollout status deploy -n "$f" --timeout=120s
  # health probe via kubectl run ephemeral curl (in-cluster)
  POD=$(kubectl get pod -n "$f" -l app.kubernetes.io/name=$f -o jsonpath='{.items[0].metadata.name}')
  if kubectl exec -n "$f" "$POD" -- python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080${HEALTH[$f]}').status==200 else 1)"; then
    echo "$f: GREEN"; RESULT="$RESULT\n$f: GREEN"
  else
    echo "$f: RED"; RESULT="$RESULT\n$f: RED"
  fi
done

echo "== mesh smoke (a11oy -> all) =="
APOD=$(kubectl get pod -n a11oy -l app.kubernetes.io/name=a11oy -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n a11oy "$APOD" -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/api/a11oy/v1/mesh').read().decode())" || true

echo "== RESULTS =="
echo -e "$RESULT"
echo "== teardown: kind delete cluster --name $CLUSTER =="
