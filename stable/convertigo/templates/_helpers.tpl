{{/*
Expand the name of the chart.
*/}}
{{- define "convertigo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 45 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 45 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "convertigo.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 45 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 45 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 45 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "convertigo.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 45 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "convertigo.labels" -}}
helm.sh/chart: {{ include "convertigo.chart" . }}
{{ include "convertigo.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "convertigo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "convertigo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "convertigo.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "convertigo.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
get run as user id
*/}}
{{ define "convertigo.runAsUserId"}}
{{- if .Values.podSecurityContext.runAsUser }}{{ .Values.podSecurityContext.runAsUser }}{{- else }}1000{{- end }}
{{- end }}

{{/*
get run as group id
*/}}
{{ define "convertigo.runAsGroupId"}}
{{- if .Values.podSecurityContext.fsGroup }}{{ .Values.podSecurityContext.fsGroup }}{{- else }}{{ template "convertigo.runAsUserId" . }}{{- end }}
{{- end }}

{{/*
Resolve CouchDB credential value from an existing secret or fallback.
*/}}
{{- define "convertigo.couchdbSecretValue" -}}
{{- $ctx := index . 0 -}}
{{- $key := index . 1 -}}
{{- $fallback := printf "%s" (index . 2) -}}
{{- $value := $fallback -}}
{{- $secretName := $ctx.Values.couchdb.existingSecret -}}
{{- if and $secretName (ne $secretName "") }}
  {{- if or (not $key) (eq $key "") }}
    {{- if not $ctx.Values.couchdb.existingSecretOptional }}
      {{- fail "couchdb.existingSecretUsernameKey/PasswordKey must be provided when couchdb.existingSecret is set" }}
    {{- end }}
  {{- else }}
    {{- $namespace := default $ctx.Release.Namespace $ctx.Values.couchdb.existingSecretNamespace -}}
    {{- $secret := lookup "v1" "Secret" $namespace $secretName -}}
    {{- if $secret }}
      {{- $data := index $secret.data $key -}}
      {{- if $data }}
        {{- $value = printf "%s" ($data | b64dec) -}}
      {{- else }}
        {{- if not $ctx.Values.couchdb.existingSecretOptional }}
          {{- fail (printf "couchdb existing secret %q is missing key %q" $secretName $key) }}
        {{- end }}
      {{- end }}
    {{- else }}
      {{- if not $ctx.Values.couchdb.existingSecretOptional }}
        {{- fail (printf "couchdb existing secret %q not found in namespace %q" $secretName $namespace) }}
      {{- end }}
    {{- end }}
  {{- end }}
{{- end }}
{{- $value | trimAll "\n\r" -}}
{{- end }}

{{/*
Resolve CouchDB username for Convertigo.
*/}}
{{- define "convertigo.couchdbUsername" -}}
{{- include "convertigo.couchdbSecretValue" (list . .Values.couchdb.existingSecretUsernameKey .Values.couchdb.admin) -}}
{{- end }}

{{/*
Resolve CouchDB password for Convertigo.
*/}}
{{- define "convertigo.couchdbPassword" -}}
{{- include "convertigo.couchdbSecretValue" (list . .Values.couchdb.existingSecretPasswordKey .Values.couchdb.password) -}}
{{- end }}

{{/*
Resolve the CouchDB URL to be used by Convertigo.
*/}}
{{- define "convertigo.couchdbUrl" -}}
{{- $default := printf "http://%s-cdb:5984" (include "convertigo.fullname" .) -}}
{{- default $default .Values.couchdb.urlOverride -}}
{{- end }}

{{/*
Compose JAVA_OPTS for the main Convertigo container.
*/}}
{{- define "convertigo.javaOpts" -}}
{{- $ctx := . -}}
{{- $timescaleJdbc := printf "jdbc:postgresql://%s-timescaledb/%s" (include "convertigo.fullname" $ctx) $ctx.Values.timescaledb.billing_database -}}
{{- $couchUser := trim (include "convertigo.couchdbUsername" $ctx) -}}
{{- $couchPass := trim (include "convertigo.couchdbPassword" $ctx) -}}
{{- $opts := list
    "-Dconvertigo.engine.log4j.appender.CemsAppender.File=/tmp/convertigo-logs/engine.log"
    (printf "-Dconvertigo.engine.fullsync.couch.username=%s" $couchUser)
    (printf "-Dconvertigo.engine.fullsync.couch.password=%s" $couchPass)
    (printf "-Dconvertigo.engine.fullsync.couch.url=%s" (include "convertigo.couchdbUrl" $ctx))
    "-Dconvertigo.engine.billing.enabled=true"
    "-Dconvertigo.engine.billing.persistence.jdbc.driver=org.postgresql.Driver"
    "-Dconvertigo.engine.billing.persistence.dialect=org.hibernate.dialect.PostgreSQLDialect"
    (printf "-Dconvertigo.engine.billing.persistence.jdbc.username=%s" $ctx.Values.timescaledb.user)
    (printf "-Dconvertigo.engine.billing.persistence.jdbc.password=%s" $ctx.Values.timescaledb.password)
    (printf "-Dconvertigo.engine.billing.persistence.jdbc.url=%s" $timescaleJdbc)
  -}}
{{- if $ctx.Values.sessionStore.enabled }}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.session.store.mode=%s" $ctx.Values.sessionStore.mode) }}
  {{- if eq $ctx.Values.sessionStore.mode "redis" }}
    {{- $redisHost := $ctx.Values.sessionStore.redis.host }}
    {{- if and (not $redisHost) $ctx.Values.redis.enabled }}
      {{- $redisHost = printf "%s-redis" (include "convertigo.fullname" $ctx) }}
    {{- end }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.host=%s" $redisHost) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.port=%v" $ctx.Values.sessionStore.redis.port) }}
    {{- if $ctx.Values.sessionStore.redis.username }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.username=%s" $ctx.Values.sessionStore.redis.username) }}
    {{- end }}
    {{- if $ctx.Values.sessionStore.redis.password }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.password=%s" $ctx.Values.sessionStore.redis.password) }}
    {{- end }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.database=%v" $ctx.Values.sessionStore.redis.database) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl=%v" $ctx.Values.sessionStore.redis.ssl) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.timeout=%v" $ctx.Values.sessionStore.redis.timeout) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.prefix=%s" $ctx.Values.sessionStore.redis.prefix) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.default.ttl=%v" $ctx.Values.sessionStore.redis.defaultTtl) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.cookie.name=%s" $ctx.Values.sessionStore.cookieName) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.serialization.debug=%v" $ctx.Values.sessionStore.serializationDebug) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.serialization.report=%v" $ctx.Values.sessionStore.serializationReport) }}
  {{- end }}
{{- end }}
{{- $extraOpts := (default (list) $ctx.Values.additionalJavaOpts) -}}
{{- range $extra := $extraOpts }}
  {{- if $extra }}
    {{- $opts = append $opts $extra }}
  {{- end }}
{{- end }}
{{- join " " $opts -}}
{{- end }}
