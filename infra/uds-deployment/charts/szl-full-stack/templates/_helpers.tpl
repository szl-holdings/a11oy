{{/*
SZL Full Stack Helm chart helpers
Doctrine v6 strict
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "szl-full-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "szl-full-stack.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label
*/}}
{{- define "szl-full-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "szl-full-stack.labels" -}}
helm.sh/chart: {{ include "szl-full-stack.chart" . }}
{{ include "szl-full-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
szl.holdings/doctrine-version: {{ .Values.global.doctrineVersion | quote }}
szl.holdings/release-version: {{ .Values.global.releaseVersion | quote }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "szl-full-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "szl-full-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
