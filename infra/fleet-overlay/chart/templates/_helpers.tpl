{{/*
SZL Fleet Overlay — Helm helper templates
Doctrine v11 LOCKED 749/14/163 at kernel commit c7c0ba17
*/}}

{{/*
Expand the chart name.
*/}}
{{- define "szl-fleet-overlay.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Chart name+version for annotations.
*/}}
{{- define "szl-fleet-overlay.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common doctrine annotations applied to all Package CRs.
*/}}
{{- define "szl-fleet.doctrineAnnotations" -}}
szl.io/doctrine-version: {{ .global.doctrinePinVersion | quote }}
szl.io/doctrine-pin: {{ .global.doctrinePinRef | quote }}
szl.io/kernel-commit: {{ .global.kernelCommit | quote }}
szl.io/slsa-level: {{ .global.slsaLevel | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" | quote }}
{{- end }}

{{/*
Generate a complete UDS Package CR for an SZL flagship app.

Usage:
  {{ include "szl-fleet.package" (dict "name" "a11oy" "app" .Values.apps.a11oy "global" .Values.global "Chart" .Chart) }}
*/}}
{{- define "szl-fleet.package" -}}
apiVersion: uds.dev/v1alpha1
kind: Package
metadata:
  name: szl-{{ .name }}
  namespace: {{ .app.namespace }}
  annotations:
    szl.io/doctrine-version: {{ .global.doctrinePinVersion | quote }}
    szl.io/doctrine-pin: {{ .global.doctrinePinRef | quote }}
    szl.io/kernel-commit: {{ .global.kernelCommit | quote }}
    szl.io/slsa-level: {{ .global.slsaLevel | quote }}
spec:
  network:
    expose:
      - host: {{ .name }}
        service: szl-{{ .name }}
        port: {{ .app.servicePort }}
        gateway: {{ .global.gatewayName }}
        selector:
          app: szl-{{ .name }}
    allow:
      - direction: Egress
        description: "Keycloak OIDC token endpoint"
        remoteNamespace: keycloak
        remoteSelector:
          app.kubernetes.io/name: keycloak
        port: 8443
        remoteProtocol: TLS
      {{- if .app.peatEnabled }}
      - direction: Egress
        description: "Peat mesh QUIC CRDT sync"
        remoteNamespace: peat-system
        remoteSelector:
          app.kubernetes.io/name: peat-mesh
        port: 4001
        remoteProtocol: UDP
      - direction: Egress
        description: "Peat mesh gRPC API"
        remoteNamespace: peat-system
        remoteSelector:
          app.kubernetes.io/name: peat-mesh
        port: 50051
        remoteProtocol: TCP
      {{- end }}
      - direction: Ingress
        description: "IntraNamespace (sidecar + health probes)"
        remoteGenerated: IntraNamespace
  sso:
    - clientId: {{ .app.clientId }}
      name: {{ .app.displayName | quote }}
      protocol: openid-connect
      redirectUris:
        - {{ printf "https://%s.%s/*" .name .global.domain | quote }}
      webOrigins:
        - {{ printf "https://%s.%s" .name .global.domain | quote }}
      standardFlowEnabled: true
      enableAuthserviceSelector:
        app: szl-{{ .name }}
      groups:
        anyOf:
          - {{ .global.ssoGroup }}
      secretConfig:
        name: szl-{{ .name }}-oidc-secret
        template: |
          OIDC_CLIENT_ID: "{{"{{"}} .clientId {{"}}"}}"
          OIDC_CLIENT_SECRET: "{{"{{"}} .secret {{"}}"}}"
          OIDC_ISSUER: "https://sso.{{ .global.domain }}/realms/uds"
  monitor:
    - description: {{ printf "szl-%s Prometheus metrics" .name | quote }}
      portName: http-metrics
      targetPort: {{ .app.metricsPort }}
      selector:
        app: szl-{{ .name }}
      path: /metrics
      kind: ServiceMonitor
{{- end }}
