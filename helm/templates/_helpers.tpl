{{/*
Chart name truncated to 63 chars.
*/}}
{{- define "node.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fullname: release-chart truncated to 63 chars.
*/}}
{{- define "node.fullname" -}}
{{- $name := .Chart.Name }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "node.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ include "node.name" . }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Geth labels.
*/}}
{{- define "node.geth.labels" -}}
{{ include "node.labels" . }}
app.kubernetes.io/component: execution
{{- end }}

{{/*
Geth selector labels.
*/}}
{{- define "node.geth.selectorLabels" -}}
app.kubernetes.io/name: {{ include "node.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: execution
{{- end }}

{{/*
Nimbus labels.
*/}}
{{- define "node.nimbus.labels" -}}
{{ include "node.labels" . }}
app.kubernetes.io/component: consensus
{{- end }}

{{/*
Nimbus selector labels.
*/}}
{{- define "node.nimbus.selectorLabels" -}}
app.kubernetes.io/name: {{ include "node.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: consensus
{{- end }}

{{/*
JWT secret name.
*/}}
{{- define "node.jwtSecretName" -}}
{{ include "node.fullname" . }}-jwt
{{- end }}

{{/*
Validate the network value.
*/}}
{{- define "node.validateNetwork" -}}
{{- $allowed := list "mainnet" "sepolia" "hoodi" -}}
{{- if not (has .Values.network $allowed) -}}
{{- fail (printf "Invalid network %q. Must be one of: %s" .Values.network (join ", " $allowed)) -}}
{{- end -}}
{{- end }}

{{/*
Geth network flag. Mainnet needs no flag; testnets use --<network>.
*/}}
{{- define "node.geth.networkFlag" -}}
{{- if ne .Values.network "mainnet" -}}
- --{{ .Values.network }}
{{- end -}}
{{- end }}

{{/*
Geth CLI arguments.
*/}}
{{- define "node.geth.args" -}}
{{- include "node.validateNetwork" . -}}
{{ include "node.geth.networkFlag" . }}
{{- if $.Values.archiveNode }}
- --syncmode=full
- --gcmode=archive
{{- end }}
{{- with .Values.geth.config }}
{{- if .http.enabled }}
- --http
- --http.addr={{ .http.addr }}
- --http.port={{ .http.port }}
- --http.api={{ .http.api }}
- --http.vhosts={{ .http.vhosts }}
{{- end }}
{{- if .ws.enabled }}
- --ws
- --ws.addr={{ .ws.addr }}
- --ws.port={{ .ws.port }}
- --ws.api={{ .ws.api }}
{{- end }}
- --authrpc.addr={{ .authrpc.addr }}
- --authrpc.port={{ .authrpc.port }}
- --authrpc.vhosts={{ .authrpc.vhosts }}
- --authrpc.jwtsecret=/secrets/jwt.hex
- --db.engine={{ .db.engine }}
- --maxpeers={{ .maxpeers }}
{{- if .metrics.enabled }}
- --metrics
- --metrics.addr={{ .metrics.addr }}
- --metrics.port={{ .metrics.port }}
{{- end }}
{{- range .extraArgs }}
- {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Nimbus CLI arguments.
*/}}
{{- define "node.nimbus.args" -}}
{{- include "node.validateNetwork" . -}}
{{- with .Values.beacon.config }}
- --network={{ $.Values.network }}
- --data-dir=/data
- --el=http://{{ include "node.fullname" $ }}-geth:{{ $.Values.geth.config.authrpc.port }}
- --jwt-secret=/secrets/jwt.hex
{{- if .rest.enabled }}
- --rest
- --rest-address={{ .rest.address }}
- --rest-port={{ .rest.port }}
{{- end }}
{{- if $.Values.archiveNode }}
- --history=archive
{{- else }}
- --history={{ .history }}
{{- end }}
{{- if .metrics.enabled }}
- --metrics
- --metrics-address={{ .metrics.address }}
- --metrics-port={{ .metrics.port }}
{{- end }}
{{- range .extraArgs }}
- {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Validate ingress path service name and beacon dependency.
*/}}
{{- define "node.validateIngressPathService" -}}
{{- $root := .root -}}
{{- $service := .service | default "" -}}
{{- $allowed := list "geth" "nimbus" -}}
{{- if not (has $service $allowed) -}}
{{- fail (printf "Invalid ingress path service %q. Must be one of: %s" $service (join ", " $allowed)) -}}
{{- end -}}
{{- if and (eq $service "nimbus") (not $root.Values.beacon.enabled) -}}
{{- fail "Ingress path service \"nimbus\" requires beacon.enabled=true" -}}
{{- end -}}
{{- end }}

{{/*
Validate all ingress paths before rendering.
*/}}
{{- define "node.validateIngressPaths" -}}
{{- range $host := .Values.ingress.hosts -}}
{{- range $path := $host.paths -}}
{{- include "node.validateIngressPathService" (dict "root" $ "service" $path.service) -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/*
Map ingress path service to backend service name.
*/}}
{{- define "node.ingressBackendServiceName" -}}
{{- if eq .service "geth" -}}
{{ include "node.fullname" .root }}-geth
{{- else if eq .service "nimbus" -}}
{{ include "node.fullname" .root }}-nimbus
{{- end -}}
{{- end }}
