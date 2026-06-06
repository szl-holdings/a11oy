{{/* Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0 */}}
{{/* Shared helpers for the SZL umbrella chart. Author: Yachay (DCO signed). */}}

{{- define "szl.namespace" -}}
{{- .Release.Namespace | default "szl-system" -}}
{{- end -}}

{{- define "szl.labels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/part-of: szl-mesh
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
helm.sh/chart: {{ .root.Chart.Name }}-{{ .root.Chart.Version }}
bigbang.dev/component: szl
{{- end -}}
