{{/*
Expand the name of the chart.
*/}}
{{- define "ffmpeg-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ffmpeg-api.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "ffmpeg-api.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ffmpeg-api.labels" -}}
helm.sh/chart: {{ include "ffmpeg-api.chart" . }}
{{ include "ffmpeg-api.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ffmpeg-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ffmpeg-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ffmpeg-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ffmpeg-api.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Common environment variables
*/}}
{{- define "ffmpeg-api.commonEnv" -}}
- name: ENVIRONMENT
  value: {{ .Values.config.environment | quote }}
- name: LOG_LEVEL
  value: {{ .Values.config.logLevel | quote }}
- name: ENABLE_METRICS
  value: {{ .Values.config.enableMetrics | quote }}
- name: METRICS_PORT
  value: {{ .Values.config.metricsPort | quote }}
{{- end }}

{{/*
Database URL construction
*/}}
{{- define "ffmpeg-api.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql://%s:%s@%s-postgresql:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password .Release.Name .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.secrets.database.url }}
{{- end }}
{{- end }}

{{/*
Redis URL construction  
*/}}
{{- define "ffmpeg-api.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.enabled }}
{{- printf "redis://:%s@%s-redis-master:6379" .Values.redis.auth.password .Release.Name }}
{{- else }}
{{- printf "redis://%s-redis-master:6379" .Release.Name }}
{{- end }}
{{- else }}
{{- .Values.secrets.redis.url }}
{{- end }}
{{- end }}