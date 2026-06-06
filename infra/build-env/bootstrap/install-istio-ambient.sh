#!/usr/bin/env bash
# install-istio-ambient.sh — Istio AMBIENT mode (ztunnel + istio-cni), NO sidecars.
# Doctrine: we are NOT Iron Bank, so we run the lighter ambient dataplane.
# Pinned to ISTIO_VERSION (default 1.25.0).
set -euo pipefail

ISTIO_VERSION="${ISTIO_VERSION:-1.25.0}"
ISTIOCTL="${ISTIOCTL:-istioctl}"
NAMESPACE="${NAMESPACE:-szl}"

echo ">> Istio ambient install (version ${ISTIO_VERSION})"
"${ISTIOCTL}" version --remote=false >/dev/null 2>&1 || true

# Install the ambient profile. This installs:
#   - istiod (control plane)
#   - istio-cni (node agent that programs ambient redirection)
#   - ztunnel (the L4 mTLS dataplane; replaces per-pod sidecars)
"${ISTIOCTL}" install --skip-confirmation \
  --set profile=ambient \
  --set values.global.istioNamespace=istio-system \
  --set meshConfig.defaultConfig.tracing.openCensusAgent.address="opentelemetry-collector.${NAMESPACE}.svc:4317" \
  --set meshConfig.enableTracing=true

echo ">> waiting for istiod + ztunnel"
kubectl -n istio-system rollout status deploy/istiod --timeout=180s
kubectl -n istio-system rollout status ds/ztunnel  --timeout=180s 2>/dev/null \
  || kubectl -n istio-system rollout status daemonset/ztunnel --timeout=180s

# Enroll the workload namespace into the ambient dataplane (L4 mTLS with zero sidecars).
kubectl label namespace "${NAMESPACE}" istio.io/dataplane-mode=ambient --overwrite

echo ">> ambient mesh ready. Namespace '${NAMESPACE}' is now ambient-enrolled."
echo "   ztunnel handles L4 mTLS; L7 routing comes from the waypoint (manifests/mesh/waypoint.yaml)."
