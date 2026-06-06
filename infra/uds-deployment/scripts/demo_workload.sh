#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# demo_workload.sh — Spin up a sample agentic workload that gets receipt-traced.
#
# Usage:
#   bash scripts/demo_workload.sh
#   # or via uds-cli:
#   uds run demo:workload
#
# What this does:
#   1. Creates the szl-demo-workload namespace
#   2. Applies a minimal Deployment (sleep container) — the Pepr policy fires
#      on admission and emits a DSSE receipt to the szl-receipts server
#   3. Applies a batch Job — same pattern, different resource type
#   4. Prints the annotated resource to show the szl.receipt.id annotation

set -euo pipefail

NAMESPACE="szl-demo-workload"
SERVER="szl-receipts-server.szl-receipts.svc.cluster.local:8080"

echo "──────────────────────────────────────────────────────"
echo " SZL Warhacker Demo — Applying sample workloads"
echo "──────────────────────────────────────────────────────"

# Create namespace
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
echo "[1/3] Namespace ${NAMESPACE} ready."

# Apply the demo Deployment — Pepr will intercept this at admission time
kubectl apply -f - <<'MANIFEST'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: szl-demo-agent
  namespace: szl-demo-workload
  labels:
    app: szl-demo-agent
    szl.io/workload-type: agentic
spec:
  replicas: 1
  selector:
    matchLabels:
      app: szl-demo-agent
  template:
    metadata:
      labels:
        app: szl-demo-agent
    spec:
      containers:
        - name: agent
          image: docker.io/library/busybox:1.36
          command: ["sh", "-c", "echo 'SZL demo agent running'; sleep 3600"]
          resources:
            requests:
              cpu: "10m"
              memory: "16Mi"
            limits:
              cpu: "50m"
              memory: "32Mi"
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: [ALL]
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        seccompProfile:
          type: RuntimeDefault
MANIFEST
echo "[2/3] Deployment szl-demo-agent applied."

# Apply a batch Job — also receipt-traced
kubectl apply -f - <<'MANIFEST'
apiVersion: batch/v1
kind: Job
metadata:
  name: szl-demo-job
  namespace: szl-demo-workload
  labels:
    szl.io/workload-type: batch
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: task
          image: docker.io/library/busybox:1.36
          command: ["sh", "-c", "echo 'SZL batch job complete'; exit 0"]
          resources:
            requests:
              cpu: "10m"
              memory: "16Mi"
            limits:
              cpu: "50m"
              memory: "32Mi"
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: [ALL]
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        seccompProfile:
          type: RuntimeDefault
MANIFEST
echo "[3/3] Job szl-demo-job applied."

echo ""
echo "Waiting 5 seconds for Pepr webhook to process…"
sleep 5

echo ""
echo "── Receipt annotations on Deployment ──────────────────"
kubectl get deployment szl-demo-agent -n "${NAMESPACE}" \
  -o jsonpath='{.metadata.annotations}' | python3 -m json.tool 2>/dev/null || \
  kubectl get deployment szl-demo-agent -n "${NAMESPACE}" -o yaml | grep "szl\."

echo ""
echo "── Receipts stored in cluster ──────────────────────────"
# Port-forward in background, query, kill
kubectl port-forward svc/szl-receipts-server 9999:8080 -n szl-receipts &
PF_PID=$!
sleep 2
curl -s http://localhost:9999/receipts | python3 -m json.tool 2>/dev/null | head -40 || \
  echo "(Could not reach receipts server — check port-forward)"
kill $PF_PID 2>/dev/null || true

echo ""
echo "Done. Check the dashboard at: http://localhost:8080 (after uds run port-forward)"
