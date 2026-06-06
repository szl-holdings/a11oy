{{- define "rosie-api.name" -}}
rosie-api
{{- end -}}

{{- define "rosie-api.labels" -}}
app.kubernetes.io/name: rosie-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "rosie-api.selectorLabels" -}}
app.kubernetes.io/name: rosie-api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
