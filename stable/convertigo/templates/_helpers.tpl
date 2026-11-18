{{/* Keep established credential wiring on upgrades, including releases predating generated Secrets. */}}
{{- define "convertigo.existingInstallation" -}}
{{- if .Release.IsUpgrade -}}true
{{- else -}}
  {{- $existing := false -}}
  {{- range $suffix := list "-c8o-workspace" "-timescaledb-workspace" "-br-workspace" "-cdb-workspace" -}}
    {{- if lookup "v1" "PersistentVolumeClaim" $.Release.Namespace (printf "%s%s" (include "convertigo.fullname" $) $suffix) -}}{{- $existing = true -}}{{- end -}}
  {{- end -}}
  {{- if $existing -}}true{{- end -}}
{{- end -}}
{{- end -}}
{{- define "convertigo.legacyCredentials" -}}
{{- $name := printf "%s-credentials" (include "convertigo.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- $saved := lookup "v1" "Secret" .Release.Namespace $name -}}
{{- $pvc := lookup "v1" "PersistentVolumeClaim" .Release.Namespace (printf "%s-c8o-workspace" (include "convertigo.fullname" .)) -}}
{{- $managed := false -}}
{{- if $pvc -}}{{- $managed = eq (dig "annotations" "convertigo.io/credential-schema" "" $pvc.metadata) "v1" -}}{{- end -}}
{{- if and (include "convertigo.existingInstallation" .) (not $saved) (not $managed) -}}true{{- end -}}
{{- end -}}

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
{{- $container := .Values.securityContext | default dict -}}
{{- $pod := .Values.podSecurityContext | default dict -}}
{{- if $container.runAsUser }}{{ $container.runAsUser }}{{- else if $pod.runAsUser }}{{ $pod.runAsUser }}{{- else }}1000{{- end }}
{{- end }}

{{/*
get run as group id
*/}}
{{ define "convertigo.runAsGroupId"}}
{{- $container := .Values.securityContext | default dict -}}
{{- $pod := .Values.podSecurityContext | default dict -}}
{{- if $container.runAsGroup }}{{ $container.runAsGroup }}{{- else if $pod.runAsGroup }}{{ $pod.runAsGroup }}{{- else if $pod.fsGroup }}{{ $pod.fsGroup }}{{- else }}{{ template "convertigo.runAsUserId" . }}{{- end }}
{{- end }}

{{/*
Resolve CouchDB credential value from an existing secret or fallback.
*/}}
{{- define "convertigo.couchdbUsername" -}}
{{- if include "convertigo.legacyCredentials" . -}}
{{- include "convertigo.couchdbSecretValue" (list . .Values.couchdb.existingSecretUsernameKey .Values.couchdb.admin) -}}
{{- else -}}{{- .Values.couchdb.admin -}}{{- end -}}
{{- end -}}
{{- define "convertigo.couchdbPassword" -}}
{{- include "convertigo.couchdbSecretValue" (list . .Values.couchdb.existingSecretPasswordKey .Values.couchdb.password) -}}
{{- end -}}

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
C8oForms plugin of Baserow, as JSON: enabled, and when enabled the archive, the ConfigMap holding it and its lock
(files/baserow-plugins/c8oforms.json). Fails on a Baserow image tag the plugin is not tested on, or on an embedded
archive that does not match its lock. Values from before the key existed (--reuse-values): disabled.
*/}}
{{- define "convertigo.baserowC8oforms" -}}
{{- $plugin := dig "plugins" "c8oforms" (dict) .Values.baserow -}}
{{- $result := dict "enabled" false -}}
{{- if and .Values.baserow.enabled $plugin.enabled -}}
  {{- $lock := .Files.Get "files/baserow-plugins/c8oforms.json" | fromJson -}}
  {{- $tag := toString .Values.baserow.image.tag -}}
  {{- if not (has $tag $lock.tested_baserow_versions) -}}
    {{- fail (printf "baserow.plugins.c8oforms (%s) is tested on Baserow %s: set baserow.image.tag to one of them, not %q (an upgrade of Baserow migrates its database)" $lock.release (join ", " $lock.tested_baserow_versions) $tag) -}}
  {{- end -}}
  {{- $path := printf "files/baserow-plugins/%s" $lock.archive -}}
  {{- $configMap := default "" $plugin.existingConfigMap -}}
  {{- if not $configMap -}}
    {{- if ne (sha256sum (.Files.Get $path)) $lock.sha256 -}}
      {{- fail (printf "%s does not match the sha256 of files/baserow-plugins/c8oforms.json" $path) -}}
    {{- end -}}
    {{- $configMap = printf "%s-c8oforms-%s" (include "convertigo.fullname" .) (trunc 16 $lock.sha256) -}}
  {{- end -}}
  {{- $result = merge (dict "enabled" true "create" (not $plugin.existingConfigMap) "configMap" $configMap "path" $path) $lock -}}
{{- end -}}
{{- toJson $result -}}
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
Resolve embedded Redis TLS secret name. Empty: the files are provided at the mount path by user volumes.
*/}}
{{- define "convertigo.redisTlsSecretName" -}}
{{- $redisTls := default dict .Values.redis.tls -}}
{{- default "" $redisTls.existingSecret -}}
{{- end }}

{{/*
Source of the embedded Redis password: file, secret, value, or empty when Redis AUTH is disabled.
*/}}
{{- define "convertigo.redisPasswordSource" -}}
{{- $prior := include "convertigo.previousEnvironment" (list . "-redis") | fromJson -}}
{{- if $prior.found -}}
  {{- range $entry := $prior.env -}}
    {{- if eq $entry.name "REDIS_PASSWORD_FILE" -}}file
    {{- else if eq $entry.name "REDIS_PASSWORD" -}}
      {{- if $entry.valueFrom -}}secret{{- else -}}value{{- end -}}
    {{- end -}}
  {{- end -}}
{{- else -}}
{{- $auth := default dict .Values.redis.auth -}}
{{- if $auth.enabled -}}
  {{- if $auth.passwordFile -}}file
  {{- else if $auth.existingSecret -}}secret
  {{- else if include "convertigo.legacyCredentials" . -}}
    {{- if $auth.password -}}value{{- end -}}
  {{- else -}}secret
  {{- end -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/*
Environment variables giving the embedded Redis password to a container (REDIS_PASSWORD or REDIS_PASSWORD_FILE).
*/}}
{{- define "convertigo.redisPasswordEnv" -}}
{{- $prior := include "convertigo.previousEnvironment" (list . "-redis") | fromJson -}}
{{- if $prior.found -}}
  {{- range $entry := $prior.env -}}
    {{- if has $entry.name (list "REDIS_PASSWORD" "REDIS_PASSWORD_FILE") -}}
{{ toYaml (list $entry) }}
    {{- end -}}
  {{- end -}}
{{- else -}}
{{- $source := include "convertigo.redisPasswordSource" . -}}
{{- if eq $source "file" }}
- name: REDIS_PASSWORD_FILE
  value: {{ .Values.redis.auth.passwordFile | quote }}
{{- else if eq $source "secret" }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.redisSecretName" . }}
      key: {{ default "redis-password" .Values.redis.auth.existingSecretPasswordKey }}
{{- else if eq $source "value" }}
- name: REDIS_PASSWORD
  value: {{ .Values.redis.auth.password | quote }}
{{- end }}
{{- end -}}
{{- end }}

{{/*
True when the embedded Redis runs with Sentinel.
*/}}
{{- define "convertigo.redisSentinel" -}}
{{- $sentinel := default dict .Values.redis.sentinel -}}
{{- if and .Values.redis.enabled $sentinel.enabled (eq (include "convertigo.sessionStoreMode" .) "redis") -}}true{{- end -}}
{{- end }}

{{/*
Host names of the embedded Redis Sentinel pods, and of their headless service.
*/}}
{{- define "convertigo.redisHeadlessHost" -}}
{{- printf "%s-redis-headless.%s.svc.%s" (include "convertigo.fullname" .) .Release.Namespace (default "cluster.local" .Values.redis.sentinel.clusterDomain) -}}
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
{{- $opts := list
    "-Dlog.directory=/tmp/convertigo-logs"
    "-Dconvertigo.engine.cache_manager.filecache.directory=/tmp/convertigo-cache"
    (printf "-Dconvertigo.engine.fullsync.couch.url=%s" (include "convertigo.couchdbUrl" $ctx))
    "-Dconvertigo.engine.billing.enabled=true"
    "-Dconvertigo.engine.billing.persistence.jdbc.driver=org.postgresql.Driver"
    "-Dconvertigo.engine.billing.persistence.dialect=org.hibernate.dialect.PostgreSQLDialect"
    (printf "-Dconvertigo.engine.billing.persistence.jdbc.username=%s" $ctx.Values.timescaledb.user)
    (printf "-Dconvertigo.engine.billing.persistence.jdbc.url=%s" $timescaleJdbc)
  -}}
{{- if include "convertigo.legacyCredentials" $ctx -}}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.fullsync.couch.username=%s" (trim (include "convertigo.couchdbUsername" $ctx))) -}}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.fullsync.couch.password=%s" (trim (include "convertigo.couchdbPassword" $ctx))) -}}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.billing.persistence.jdbc.password=%s" $ctx.Values.timescaledb.password) -}}
{{- end -}}
{{- $sessionMode := include "convertigo.sessionStoreMode" $ctx -}}
{{- $sessionRedis := default dict $ctx.Values.sessionStore.redis -}}
{{- $redisTopology := default "single" $sessionRedis.topology -}}
{{- $sentinel := default dict $sessionRedis.sentinel -}}
{{- $sentinelNodes := list -}}
{{- $embeddedSentinel := include "convertigo.redisSentinel" $ctx -}}
{{- if not (has $redisTopology (list "single" "sentinel")) -}}
  {{- fail "sessionStore.redis.topology must be single or sentinel" -}}
{{- end -}}
{{- if $embeddedSentinel -}}
  {{- $redisTopology = "sentinel" -}}
  {{- $sentinel = dict "master" $ctx.Values.redis.sentinel.masterName -}}
  {{- if not (regexMatch "^[a-zA-Z0-9_.-]+$" (toString $sentinel.master)) -}}
    {{- fail "redis.sentinel.masterName must contain only letters, digits, dots, underscores or hyphens" -}}
  {{- end -}}
  {{- $replicas := int $ctx.Values.redis.sentinel.replicas -}}
  {{- if lt $replicas 3 -}}
    {{- fail "redis.sentinel.replicas must be at least 3" -}}
  {{- end -}}
  {{- range $i := until $replicas -}}
    {{- $sentinelNodes = append $sentinelNodes (printf "%s-redis-%d.%s:%v" (include "convertigo.fullname" $ctx) $i (include "convertigo.redisHeadlessHost" $ctx) $ctx.Values.redis.sentinel.port) -}}
  {{- end -}}
{{- else if eq $redisTopology "sentinel" -}}
  {{- if or $ctx.Values.redis.enabled (ne $sessionMode "redis") -}}
    {{- fail "Sentinel requires sessionStore.mode=redis, and either redis.enabled=true with redis.sentinel.enabled=true, or redis.enabled=false with an external Redis/Sentinel" -}}
  {{- end -}}
  {{- if or (not (trim (toString (default "" $sentinel.master)))) (not $sentinel.nodes) -}}
    {{- fail "Sentinel requires sessionStore.redis.sentinel.master and sessionStore.redis.sentinel.nodes" -}}
  {{- end -}}
  {{- if not (regexMatch "^[a-zA-Z0-9_.-]+$" (toString $sentinel.master)) -}}
    {{- fail "sessionStore.redis.sentinel.master must contain only letters, digits, dots, underscores or hyphens" -}}
  {{- end -}}
  {{- $nodes := $sentinel.nodes -}}
  {{- if kindIs "string" $nodes -}}
    {{- $nodes = regexSplit "[,[:space:]]+" (trim $nodes) -1 -}}
  {{- else if not (kindIs "slice" $nodes) -}}
    {{- fail "sessionStore.redis.sentinel.nodes must be a host:port list or comma-separated string" -}}
  {{- end -}}
  {{- range $node := $nodes -}}
    {{- $node = trim (toString $node) -}}
    {{- if not (regexMatch "^([a-zA-Z0-9.-]+|\\[[0-9a-fA-F:.%]+\\]):[0-9]+$" $node) -}}
      {{- fail "sessionStore.redis.sentinel.nodes must contain host:port addresses without credentials" -}}
    {{- end -}}
    {{- $port := atoi (last (splitList ":" $node)) -}}
    {{- if or (lt $port 1) (gt $port 65535) -}}
      {{- fail "sessionStore.redis.sentinel.nodes ports must be between 1 and 65535" -}}
    {{- end -}}
    {{- $sentinelNodes = append $sentinelNodes $node -}}
  {{- end -}}
{{- end -}}
{{- $sessionRedisSsl := default dict $sessionRedis.ssl -}}
{{- $redisTls := default dict $ctx.Values.redis.tls -}}
{{- $redisTlsMountPath := include "convertigo.redisTlsMountPath" $ctx -}}
{{- $redisTlsClientTruststoreKey := default "truststore.p12" $redisTls.clientTruststoreKey -}}
{{- $redisTlsClientKeystoreKey := default "client.p12" $redisTls.clientKeystoreKey -}}
{{- $redisTlsUseClientKeystore := and $redisTls.authClients $redisTlsClientKeystoreKey -}}
{{- if eq $sessionMode "redis" }}
  {{- $opts = append $opts "-Dconvertigo.engine.session.store.mode=redis" }}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.topology=%s" $redisTopology) }}
  {{- with $sessionRedis.startupFallback }}
    {{- if not (has (toString .) (list "none" "tomcat")) }}
      {{- fail "sessionStore.redis.startupFallback must be none or tomcat" -}}
    {{- end }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.startup.fallback=%s" .) }}
  {{- end }}
  {{- with $sessionRedis.readinessGrace }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.readiness.grace=%v" .) }}
  {{- end }}
  {{- if eq $redisTopology "sentinel" }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.sentinel.master=%s" $sentinel.master) }}
    {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.sentinel.nodes=%s" (join "," (uniq $sentinelNodes))) }}
    {{- with $sentinel.username }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.sentinel.username=%s" .) }}
    {{- end }}
    {{- with $sentinel.password }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.sentinel.password=%s" .) }}
    {{- end }}
  {{- end }}
  {{- if $ctx.Values.redis.enabled }}
    {{- if not $embeddedSentinel }}
      {{- $redisHost := printf "%s-redis" (include "convertigo.fullname" $ctx) -}}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.host=%s" $redisHost) }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.port=%v" $ctx.Values.redis.service.port) }}
    {{- end }}
    {{- $passwordSource := include "convertigo.redisPasswordSource" $ctx -}}
    {{- if eq $passwordSource "value" }}
      {{- $opts = append $opts (printf "-Dconvertigo.engine.session.redis.password=%s" $ctx.Values.redis.auth.password) }}

    {{- else if and (eq $passwordSource "secret") (include "convertigo.legacyCredentials" $ctx) }}
      {{- $opts = append $opts "-Dconvertigo.engine.session.redis.password=$(REDIS_PASSWORD)" }}
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
{{- if (default dict $ctx.Values.localWork).enabled }}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.local_work.directory=%s" $ctx.Values.localWork.mountPath) }}
{{- end }}
{{- /* imposed only when set: empty leaves the decision to the configuration of the server */ -}}
{{- with $ctx.Values.webStudio }}
  {{- if not (has (toString .) (list "disabled" "enabled")) }}
    {{- fail (printf "webStudio must be disabled or enabled, not %v" .) }}
  {{- end }}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.web_studio=%s" (toString .)) }}
{{- end }}
{{- with $ctx.Values.serverBuild }}
  {{- if not (has (toString .) (list "none" "sources" "studio" "all")) }}
    {{- fail (printf "serverBuild must be none, sources, studio or all, not %v" .) }}
  {{- end }}
  {{- $opts = append $opts (printf "-Dconvertigo.engine.server_build=%s" (toString .)) }}
{{- end }}
{{- $extraOpts := (default (list) $ctx.Values.additionalJavaOpts) -}}
{{- range $extra := $extraOpts }}
  {{- if $extra }}
    {{- $opts = append $opts $extra }}
  {{- end }}
{{- end }}
{{- join " " $opts -}}
{{- end }}

{{/* Admin credentials are mounted only in the workspace init container. */}}
{{- define "convertigo.adminSecretName" -}}
{{- $admin := default dict .Values.admin -}}
{{- if not (regexMatch "^[A-Za-z0-9_.-]+$" (default "password" $admin.passwordKey)) -}}
{{- fail "admin.passwordKey must be a Secret data key" -}}
{{- end -}}
{{- if not (regexMatch "^[A-Za-z0-9_.@-]+$" (default "admin" $admin.username)) -}}
{{- fail "admin.username must be a single account identifier" -}}
{{- end -}}

{{- default (printf "%s-admin" (include "convertigo.fullname" .)) $admin.existingSecret -}}
{{- end -}}

{{/* Installation credential references. */}}
{{- define "convertigo.installationSecretName" -}}
{{- $cfg := .Values.credentials | default dict -}}
{{- $name := printf "%s-credentials" (include "convertigo.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- default $name $cfg.existingSecret -}}
{{- end -}}
{{/* No custom phrase is inferred from the general installation Secret. */}}
{{- define "convertigo.customPassphrase" -}}
{{- $crypto := .Values.crypto | default dict -}}
{{- if or $crypto.passphrase $crypto.existingSecret -}}true{{- end -}}
{{- end -}}
{{- define "convertigo.cryptoSecretName" -}}
{{- default (printf "%s-crypto" (include "convertigo.fullname" .) | trunc 63 | trimSuffix "-") (.Values.crypto | default dict).existingSecret -}}
{{- end -}}
{{- define "convertigo.baserowAdminSecretName" -}}{{- default (include "convertigo.installationSecretName" .) ((.Values.baserow.admin | default dict).existingSecret) -}}{{- end -}}
{{- define "convertigo.timescaleSecretName" -}}{{- default (include "convertigo.installationSecretName" .) .Values.timescaledb.existingSecret -}}{{- end -}}
{{- define "convertigo.baserowDatabaseSecretName" -}}{{- default (include "convertigo.installationSecretName" .) .Values.baserow.existingSecret -}}{{- end -}}
{{- define "convertigo.couchSecretName" -}}
{{- if and (not (include "convertigo.legacyCredentials" .)) .Values.couchdb.existingSecretNamespace (ne .Values.couchdb.existingSecretNamespace .Release.Namespace) -}}
{{- fail "CouchDB credential Secrets must be in the release namespace" -}}
{{- end -}}
{{- default (include "convertigo.installationSecretName" .) .Values.couchdb.existingSecret -}}{{- end -}}
{{- define "convertigo.redisSecretName" -}}{{- default (include "convertigo.installationSecretName" .) .Values.redis.auth.existingSecret -}}{{- end -}}

{{- define "convertigo.baserowDatabaseEnv" -}}
- name: BASEROW_PUBLIC_URL
  value: {{ include "convertigo.baserowPublicUrl" . | quote }}
- name: DATABASE_HOST
  value: {{ printf "%s-timescaledb" (include "convertigo.fullname" .) | quote }}
- name: DATABASE_PORT
  value: "5432"
- name: DATABASE_NAME
  value: {{ .Values.baserow.baserow_db | quote }}
- name: DATABASE_USER
  value: {{ .Values.baserow.baserow_user | quote }}
- name: DATABASE_PASSWORD
  {{- if and (include "convertigo.legacyCredentials" .) (not .Values.baserow.existingSecret) }}
  value: {{ .Values.baserow.baserow_password | quote }}
  {{- else }}
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.baserowDatabaseSecretName" . }}
      key: {{ default "baserow-database-password" .Values.baserow.existingSecretPasswordKey }}
{{- end }}
{{- end -}}

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

{{/* On an upgrade the live workload is the authority for established credentials,
including default values not present in the release's user-supplied values. */}}
{{- define "convertigo.previousEnvironment" -}}
{{- $ctx := index . 0 -}}{{- $suffix := index . 1 -}}
{{- $result := dict "found" false "env" (list) -}}
{{- if include "convertigo.existingInstallation" $ctx -}}
  {{- $name := printf "%s%s" (include "convertigo.fullname" $ctx) $suffix -}}
  {{- $object := lookup "apps/v1" "Deployment" $ctx.Release.Namespace $name -}}
  {{- if and (not $object) (eq $suffix "-redis") -}}
    {{- $object = lookup "apps/v1" "StatefulSet" $ctx.Release.Namespace $name -}}
  {{- end -}}
  {{- if $object -}}
    {{- $result = dict "found" true "env" ((first $object.spec.template.spec.containers).env | default (list)) -}}
  {{- end -}}
{{- end -}}
{{- toJson $result -}}
{{- end -}}

{{/* Preserve established account/connection entries while allowing unrelated settings to evolve.
JAVA_OPTS is atomic because historical credentials can be embedded in arbitrary JVM arguments. */}}
{{- define "convertigo.componentEnvironment" -}}
{{- $ctx := index . 0 -}}{{- $suffix := index . 1 -}}{{- $current := index . 2 | fromYamlArray -}}
{{- range $entry := $current -}}
  {{- if not (kindIs "map" $entry) -}}{{- fail "Invalid component environment YAML" -}}{{- end -}}
  {{- if not $entry.name -}}{{- fail "Component environment entry is missing its name" -}}{{- end -}}
{{- end -}}
{{- $protected := index . 3 -}}
{{- $prior := include "convertigo.previousEnvironment" (list $ctx $suffix) | fromJson -}}
{{- if not $prior.found -}}{{- toYaml $current -}}
{{- else -}}
  {{- $byName := dict -}}{{- range $current -}}{{- $_ := set $byName .name . -}}{{- end -}}
  {{- $seen := dict -}}{{- $result := list -}}
  {{- range $entry := $prior.env -}}
    {{- $_ := set $seen $entry.name true -}}
    {{- if has $entry.name $protected -}}{{- $result = append $result $entry -}}
    {{- else if hasKey $byName $entry.name -}}{{- $result = append $result (get $byName $entry.name) -}}
    {{- end -}}
  {{- end -}}
  {{- range $entry := $current -}}
    {{- if and (not (hasKey $seen $entry.name)) (not (has $entry.name $protected)) -}}
      {{- $result = append $result $entry -}}
    {{- end -}}
  {{- end -}}
  {{- toYaml $result -}}
{{- end -}}
{{- end -}}

{{- define "convertigo.defaultEnvironment_convertigo" -}}
{{- $embeddedRedis := and (eq (include "convertigo.sessionStoreMode" .) "redis") .Values.redis.enabled -}}
{{- $prior := include "convertigo.previousEnvironment" (list . "-convertigo") | fromJson -}}
{{- $javaOpts := "" -}}
{{- if $prior.found -}}
  {{- range $prior.env -}}{{- if eq .name "JAVA_OPTS" -}}{{- $javaOpts = .value -}}{{- end -}}{{- end -}}
{{- else -}}{{- $javaOpts = include "convertigo.javaOpts" . -}}{{- end -}}
{{- if and $embeddedRedis (include "convertigo.legacyCredentials" .) }}
{{- include "convertigo.redisPasswordEnv" . | trim | nindent 0 }}
{{- end }}
- name: JAVA_OPTS
  value: {{ $javaOpts | quote }}
- name: JXMX
  value: '{{ .Values.image.jxmx }}'
- name: LOG_STDOUT
  value: "true"
- name: LOG_FILE
  value: "true"
- name: COOKIE_PATH
  value: "/convertigo"
- name: COOKIE_SECURE
  value: "{{ .Values.ssl_only }}"
- name: COOKIE_SAMESITE
  value: lax
- name: SESSION_TIMEOUT
  value: "30"
- name: DISABLE_SUDO
  value: "false"
- name: PUBLIC_DOMAINS
  value: {{ include "convertigo.publicDomains" . | quote }}
- name: BASEROW_PUBLIC_URL
  value: {{ include "convertigo.baserowPublicUrl" . | quote }}
{{- end -}}

{{- define "convertigo.defaultEnvironment_timescale" -}}
{{- $prior := include "convertigo.previousEnvironment" (list . "-timescale") | fromJson -}}
{{- if $prior.found -}}{{- toYaml $prior.env -}}{{- else -}}
- name: PGDATA
  value: /var/lib/postgresql/data/pgdata
- name: POSTGRES_PASSWORD
  {{- if and (include "convertigo.legacyCredentials" .) (not .Values.timescaledb.existingSecret) }}
  value: {{ .Values.timescaledb.password | quote }}
  {{- else }}
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.timescaleSecretName" . }}
      key: {{ default "postgres-password" .Values.timescaledb.existingSecretPasswordKey }}
  {{- end }}
- name: POSTGRES_USER
  value: "{{ .Values.timescaledb.user }}"
- name: BILLING_DB
  value: "{{ .Values.timescaledb.billing_database }}"
- name: BILLING_PASSWORD
  {{- if and (include "convertigo.legacyCredentials" .) (not .Values.timescaledb.existingSecret) }}
  value: {{ .Values.timescaledb.billing_password | quote }}
  {{- else }}
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.timescaleSecretName" . }}
      key: {{ default "billing-password" .Values.timescaledb.existingSecretBillingPasswordKey }}
  {{- end }}
- name: BILLING_USER
  value: "{{ .Values.timescaledb.billing_user }}"
- name: BASEROW_DB
  value: "{{ .Values.baserow.baserow_db }}"
- name: BASEROW_USER
  value: "{{ .Values.baserow.baserow_user }}"
- name: BASEROW_PASSWORD
  {{- if and (include "convertigo.legacyCredentials" .) (not .Values.baserow.existingSecret) }}
  value: {{ .Values.baserow.baserow_password | quote }}
  {{- else }}
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.baserowDatabaseSecretName" . }}
      key: {{ default "baserow-database-password" .Values.baserow.existingSecretPasswordKey }}
  {{- end }}

{{- end -}}
{{- end -}}

{{- define "convertigo.defaultEnvironment_br" -}}
{{- $c8oforms := include "convertigo.baserowC8oforms" . | fromJson -}}
{{- include "convertigo.baserowDatabaseEnv" . | nindent 0 }}
- name: BASEROW_EXTRA_ALLOWED_HOSTS
  value: "*"
{{- if $c8oforms.enabled }}
# Next to the mount: a container with the variable and without the file does not start.
- name: BASEROW_PLUGIN_URLS
  value: {{ printf "file:///c8o-plugins/%s" $c8oforms.archive | quote }}
# The image installs the plugin with pip, by default in an isolated build environment that downloads
# setuptools from PyPI: without Internet access, Baserow would not start. "false" (sic, pip inverts
# this variable) builds it with the setuptools of the image instead, offline.
- name: PIP_NO_BUILD_ISOLATION
  value: "false"
{{- end }}
{{- end -}}

{{- define "convertigo.defaultEnvironment_cdb" -}}
{{- $prior := include "convertigo.previousEnvironment" (list . "-cdb") | fromJson -}}
{{- /* The server uuid (convertigo.couchdbUuid) is not an established credential: always the current reference. */ -}}
{{- $uuid := dict "name" "C8O_COUCHDB_UUID" "valueFrom" (dict "configMapKeyRef" (dict "name" (printf "%s-cdb-uuid" (include "convertigo.fullname" .)) "key" "uuid")) -}}
{{- if $prior.found -}}
  {{- $env := list -}}
  {{- range $entry := $prior.env -}}{{- if ne $entry.name "C8O_COUCHDB_UUID" -}}{{- $env = append $env $entry -}}{{- end -}}{{- end -}}
  {{- toYaml (append $env $uuid) -}}
{{- else -}}
- name: COUCHDB_USER
  {{- if and (not (include "convertigo.legacyCredentials" .)) .Values.couchdb.existingSecretUsernameKey }}
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.couchSecretName" . }}
      key: {{ .Values.couchdb.existingSecretUsernameKey }}
  {{- else }}
  value: {{ include "convertigo.couchdbUsername" . | quote }}
  {{- end }}
- name: COUCHDB_PASSWORD
  {{- if include "convertigo.legacyCredentials" . }}
  value: {{ include "convertigo.couchdbPassword" . | quote }}
  {{- else }}
  valueFrom:
    secretKeyRef:
      name: {{ include "convertigo.couchSecretName" . }}
      key: {{ default "couchdb-password" .Values.couchdb.existingSecretPasswordKey }}
  {{- end }}
{{ toYaml (list $uuid) }}
{{- end -}}
{{- end -}}

{{/* A new default database tag must not upgrade an existing database implicitly. */}}
{{- define "convertigo.timescaleImage" -}}
{{- $image := printf "%s:%s" .Values.timescaledb.image.repository .Values.timescaledb.image.tag -}}
{{- if include "convertigo.existingInstallation" . -}}
  {{- $prior := lookup "apps/v1" "Deployment" .Release.Namespace (printf "%s-timescale" (include "convertigo.fullname" .)) -}}
  {{- if $prior -}}{{- $image = (first $prior.spec.template.spec.containers).image -}}{{- end -}}
{{- end -}}
{{- $image -}}
{{- end -}}

{{/*
Single-pod Deployment on a ReadWriteOnce volume (CouchDB, TimescaleDB, a lone Convertigo): the old pod must end
before the new one starts, or two processes share the same data on one node, and a new pod on another node waits
forever for the volume. maxSurge 0 removes the old pod first; the required anti-affinity of
convertigo.singlePodAffinity keeps the new pod off a node where the old one is still terminating. RWO volume
attachment serializes access when the replacement is on another node; this is not fencing for shared storage or
an unreachable old node. Switching an existing Deployment to Recreate can fail with server-side apply (Helm 4)
when Kubernetes keeps defaulted rollingUpdate settings. Explicit RWX database storage retains Recreate.
*/}}
{{- define "convertigo.singlePodStrategy" -}}
type: RollingUpdate
rollingUpdate:
  maxSurge: 0
  maxUnavailable: 1
{{- end -}}

{{/*
Affinity of a single-pod Deployment: the given affinity, plus a required anti-affinity with its own pods per node.
Argument: dict with "labels" (pod selector labels as YAML) and "affinity" (optional user affinity).
*/}}
{{- define "convertigo.singlePodAffinity" -}}
{{- $affinity := deepCopy (default dict .affinity) -}}
{{- $anti := default dict $affinity.podAntiAffinity -}}
{{- $required := default list $anti.requiredDuringSchedulingIgnoredDuringExecution -}}
{{- $term := dict "topologyKey" "kubernetes.io/hostname" "labelSelector" (dict "matchLabels" (fromYaml .labels)) -}}
{{- $_ := set $anti "requiredDuringSchedulingIgnoredDuringExecution" (append $required $term) -}}
{{- $_ := set $affinity "podAntiAffinity" $anti -}}
{{- toYaml $affinity -}}
{{- end -}}

{{/*
CouchDB server uuid: couchdb.uuid, else the one kept in the ConfigMap <release>-cdb-uuid, else a new one. It must
stay stable: FullSync clients (PouchDB) derive their replication id from it and restart from the beginning of the
changes feed when it changes.
*/}}
{{- define "convertigo.couchdbUuid" -}}
{{- $provided := toString (default "" (default dict .Values.couchdb).uuid) -}}
{{- if $provided -}}
  {{- if not (regexMatch "^[0-9a-f]{32}$" $provided) -}}
    {{- fail "couchdb.uuid must be 32 lowercase hexadecimal characters" -}}
  {{- end -}}
  {{- $provided -}}
{{- else -}}
  {{- $previous := lookup "v1" "ConfigMap" .Release.Namespace (printf "%s-cdb-uuid" (include "convertigo.fullname" .)) | default dict -}}
  {{- $kept := toString (index (default dict $previous.data) "uuid" | default "") -}}
  {{- if regexMatch "^[0-9a-f]{32}$" $kept -}}{{- $kept -}}{{- else -}}{{- uuidv4 | replace "-" "" -}}{{- end -}}
{{- end -}}
{{- end -}}
