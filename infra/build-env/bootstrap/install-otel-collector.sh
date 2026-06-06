#!/usr/bin/env bash
# install-otel-collector.sh — OpenTelemetry Collector (OTLP broker) + Jaeger all-in-one.
# The collector is the cross-pod OTLP broker that closes the honest gap in a11oy's
# mesh role: organs export OTLP -> collector -> Jaeger, so a single traceparent
# is visible end-to-end across all 5 organs.
set -euo pipefail

OTEL_VERSION="${OTEL_VERSION:-0.135.0}"
NAMESPACE="${NAMESPACE:-szl}"

echo ">> deploying Jaeger all-in-one (trace backend + UI on host :16686)"
kubectl -n "${NAMESPACE}" apply -f - <<'YAML'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  labels: { app: jaeger }
spec:
  replicas: 1
  selector: { matchLabels: { app: jaeger } }
  template:
    metadata: { labels: { app: jaeger } }
    spec:
      containers:
        - name: jaeger
          image: jaegertracing/all-in-one:1.62.0
          env:
            - { name: COLLECTOR_OTLP_ENABLED, value: "true" }
          ports:
            - { containerPort: 16686, name: ui }
            - { containerPort: 4317,  name: otlp-grpc }
            - { containerPort: 4318,  name: otlp-http }
---
apiVersion: v1
kind: Service
metadata: { name: jaeger }
spec:
  selector: { app: jaeger }
  ports:
    - { name: ui,        port: 16686, targetPort: 16686 }
    - { name: otlp-grpc, port: 4317,  targetPort: 4317 }
    - { name: otlp-http, port: 4318,  targetPort: 4318 }
---
# NodePort so the Jaeger UI is reachable on host localhost:16686 (mapped in kind/cluster.yaml)
apiVersion: v1
kind: Service
metadata: { name: jaeger-ui-np }
spec:
  type: NodePort
  selector: { app: jaeger }
  ports:
    - { name: ui, port: 16686, targetPort: 16686, nodePort: 30686 }
YAML

echo ">> deploying OpenTelemetry Collector (contrib ${OTEL_VERSION})"
# Render the collector config from manifests/otel/collector.yaml as a ConfigMap,
# then run the collector pointing at it.
kubectl -n "${NAMESPACE}" create configmap otel-collector-config \
  --from-file=collector.yaml="$(dirname "$0")/../manifests/otel/collector.yaml" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "${NAMESPACE}" apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opentelemetry-collector
  labels: { app: opentelemetry-collector }
spec:
  replicas: 1
  selector: { matchLabels: { app: opentelemetry-collector } }
  template:
    metadata: { labels: { app: opentelemetry-collector } }
    spec:
      containers:
        - name: otc
          image: otel/opentelemetry-collector-contrib:${OTEL_VERSION}
          args: ["--config=/conf/collector.yaml"]
          ports:
            - { containerPort: 4317, name: otlp-grpc }
            - { containerPort: 4318, name: otlp-http }
            - { containerPort: 8889, name: prometheus }
          volumeMounts:
            - { name: conf, mountPath: /conf }
      volumes:
        - name: conf
          configMap: { name: otel-collector-config }
---
apiVersion: v1
kind: Service
metadata: { name: opentelemetry-collector }
spec:
  selector: { app: opentelemetry-collector }
  ports:
    - { name: otlp-grpc, port: 4317, targetPort: 4317 }
    - { name: otlp-http, port: 4318, targetPort: 4318 }
YAML

kubectl -n "${NAMESPACE}" rollout status deploy/jaeger --timeout=120s
kubectl -n "${NAMESPACE}" rollout status deploy/opentelemetry-collector --timeout=120s
echo ">> OTLP broker ready. Organs should export to opentelemetry-collector.${NAMESPACE}.svc:4317"
