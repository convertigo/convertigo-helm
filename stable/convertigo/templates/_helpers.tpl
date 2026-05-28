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
Resolve the external public origin used by browser clients.
*/}}
{{- define "convertigo.publicUrl" -}}
{{- default (printf "https://%s" .Values.publicAddr) .Values.publicUrl | trimSuffix "/" -}}
{{- end }}

{{/*
Resolve Convertigo public CORS origins passed to the Docker entrypoint.
*/}}
{{- define "convertigo.publicDomains" -}}
{{- default (include "convertigo.publicUrl" .) .Values.publicDomains -}}
{{- end }}

{{/*
Resolve the external Baserow URL.
*/}}
{{- define "convertigo.baserowPublicUrl" -}}
{{- default (include "convertigo.publicUrl" .) .Values.baserow.baserow_public_url -}}
{{- end }}

{{/*
Resolve session store mode.
auto -> redis when redis.enabled=true, otherwise tomcat.
*/}}
{{- define "convertigo.sessionStoreMode" -}}
{{- $mode := default "auto" .Values.sessionStore.mode -}}
{{- if eq $mode "auto" -}}
  {{- if .Values.redis.enabled -}}redis{{- else -}}tomcat{{- end -}}
{{- else -}}
  {{- $mode -}}
{{- end -}}
{{- end }}

{{/*
Resolve embedded Redis TLS secret name.
*/}}
{{- define "convertigo.redisTlsSecretName" -}}
{{- $redisTls := default dict .Values.redis.tls -}}
{{- required "redis.tls.existingSecret must be set when redis.tls.enabled=true" $redisTls.existingSecret -}}
{{- end }}

{{/*
Resolve embedded Redis TLS mount path.
*/}}
{{- define "convertigo.redisTlsMountPath" -}}
{{- $redisTls := default dict .Values.redis.tls -}}
{{- default "/etc/convertigo/redis-tls" $redisTls.mountPath -}}
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
    "-Dlog.directory=/tmp/convertigo-logs"
    "-Dconvertigo.engine.cache_manager.filecache.directory=/tmp/convertigo-cache"
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
{{- $sessionMode := include "convertigo.sessionStoreMode" $ctx -}}
{{- $sessionRedis := default dict $ctx.Values.sessionStore.redis -}}
{{- $sessionRedisSsl := default dict $sessionRedis.ssl -}}
{{- $redisTls := default dict $ctx.Values.redis.tls -}}
{{- $redisTlsMountPath := include "convertigo.redisTlsMountPath" $ctx -}}
{{- $redisTlsClientTruststoreKey := default "truststore.p12" $redisTls.clientTruststoreKey -}}
{{- $redisTlsClientKeystoreKey := default "client.p12" $redisTls.clientKeystoreKey -}}
{{- $redisTlsUseClientKeystore := and $redisTls.authClients $redisTlsClientKeystoreKey -}}
{{- if eq $sessionMode "redis" }}
  {{- $opts = append $opts "-Dconvertigo.engine.session.store.mode=redis" }}
  {{- if $ctx.Values.redis.enabled }}
    {{- $redisHost := printf "%s-redis" (include "convertigo.fullname" $ctx) -}}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.host=%s" $redisHost) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.port=%v" $ctx.Values.redis.service.port) }}
    {{- if and $ctx.Values.redis.auth.enabled $ctx.Values.redis.auth.password }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.password=%s" $ctx.Values.redis.auth.password) }}
    {{- end }}
  {{- else }}
    {{- with $sessionRedis.host }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.host=%s" .) }}
    {{- end }}
    {{- with $sessionRedis.port }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.port=%v" .) }}
    {{- end }}
    {{- with $sessionRedis.username }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.username=%s" .) }}
    {{- end }}
    {{- with $sessionRedis.password }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.password=%s" .) }}
    {{- end }}
    {{- with $sessionRedis.database }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.database=%v" .) }}
    {{- end }}
  {{- end }}
  {{- if and $ctx.Values.redis.enabled $redisTls.enabled }}
    {{- $opts = append $opts "-Dconvertigo.engine.session.redis.ssl=true" }}
    {{- with $redisTlsClientTruststoreKey }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.truststore=%s/%s" $redisTlsMountPath .) }}
    {{- end }}
    {{- with $redisTls.truststorePassword }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.truststore.password=%s" .) }}
    {{- end }}
    {{- if $redisTlsUseClientKeystore }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.keystore=%s/%s" $redisTlsMountPath $redisTlsClientKeystoreKey) }}
      {{- with $redisTls.keystorePassword }}
        {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.keystore.password=%s" .) }}
      {{- end }}
      {{- with $redisTls.keystoreType }}
        {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.keystore.type=%s" .) }}
      {{- end }}
    {{- end }}
    {{- with $redisTls.verificationMode }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.verification.mode=%s" .) }}
    {{- end }}
    {{- with $redisTls.protocols }}
      {{- if kindIs "slice" . }}
        {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.protocols=%s" (join "," .)) }}
      {{- else }}
        {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.protocols=%s" .) }}
      {{- end }}
    {{- end }}
  {{- else }}
    {{- if $sessionRedisSsl.enabled }}
      {{- $opts = append $opts "-Dconvertigo.engine.session.redis.ssl=true" }}
    {{- end }}
    {{- with $sessionRedisSsl.truststore }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.truststore=%s" .) }}
    {{- end }}
    {{- with $sessionRedisSsl.truststorePassword }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.truststore.password=%s" .) }}
    {{- end }}
    {{- with $sessionRedisSsl.keystore }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.keystore=%s" .) }}
    {{- end }}
    {{- with $sessionRedisSsl.keystorePassword }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.keystore.password=%s" .) }}
    {{- end }}
    {{- with $sessionRedisSsl.keystoreType }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.keystore.type=%s" .) }}
    {{- end }}
    {{- with $sessionRedisSsl.verificationMode }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.verification.mode=%s" .) }}
    {{- end }}
    {{- with $sessionRedisSsl.protocols }}
      {{- if kindIs "slice" . }}
        {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.protocols=%s" (join "," .)) }}
      {{- else }}
        {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.ssl.protocols=%s" .) }}
      {{- end }}
    {{- end }}
  {{- end }}
{{- end }}
{{- if $ctx.Values.sharedWorkspaceSync.enabled }}
  {{- $opts = append $opts "-Dconvertigo.engine.session.shared_workspace.sync.enabled=true" }}
{{- end }}
{{- $extraOpts := (default (list) $ctx.Values.additionalJavaOpts) -}}
{{- range $extra := $extraOpts }}
  {{- if $extra }}
    {{- $opts = append $opts $extra }}
  {{- end }}
{{- end }}
{{- join " " $opts -}}
{{- end }}
