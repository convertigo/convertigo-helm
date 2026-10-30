#!/usr/bin/env bash
set -euo pipefail

# Rendering only: no cluster access or deployment, credentials are test values.
chart="$(cd "$(dirname "$0")/../stable/convertigo" && pwd)"
base=(--set sessionStore.mode=redis --set sessionStore.redis.topology=sentinel
  --set sessionStore.redis.sentinel.master=mymaster
  --set-json 'sessionStore.redis.sentinel.nodes=["sentinel-0:26379","sentinel-1:26379","sentinel-2:26379"]')

expect_option() {
  [[ "$rendered" == *"$1"* ]] || { echo "Missing option: $1" >&2; exit 1; }
}
expect_failure() {
  local output
  if output=$(helm template sentinel "$chart" "$@" 2>&1); then
    echo "Invalid configuration was accepted" >&2
    exit 1
  fi
  [[ "$output" == *"sessionStore"* || "$output" == *"Sentinel requires"* || "$output" == *"redis.sentinel"* ]] || {
    echo "Unexpected rendering failure: $output" >&2; exit 1;
  }
}

helm lint "$chart"
rendered=$(helm template default "$chart")
[[ "$rendered" != *"-Dconvertigo.engine.session.store.mode=redis"* ]]
rendered=$(helm template embedded "$chart" --set redis.enabled=true)
expect_option '-Dconvertigo.engine.session.redis.topology=single'
expect_option '-Dconvertigo.engine.session.redis.host=embedded-convertigo-redis'
rendered=$(helm template external "$chart" --set sessionStore.mode=redis --set sessionStore.redis.host=redis-external --set sessionStore.redis.port=6380)
expect_option '-Dconvertigo.engine.session.redis.host=redis-external'
expect_option '-Dconvertigo.engine.session.redis.port=6380'
secure=(--set sessionStore.redis.username=data-user
  --set sessionStore.redis.password=data-test-password --set sessionStore.redis.database=2
  --set sessionStore.redis.sentinel.username=sentinel-user --set sessionStore.redis.sentinel.password=sentinel-test-password
  --set sessionStore.redis.ssl.enabled=true --set sessionStore.redis.ssl.truststore=/tls/ca.p12
  --set sessionStore.redis.ssl.keystore=/tls/client.p12 --set sessionStore.redis.ssl.keystoreType=PKCS12)
rendered=$(helm template sentinel "$chart" "${base[@]}" "${secure[@]}")
expect_option '-Dconvertigo.engine.session.redis.topology=sentinel'
expect_option '-Dconvertigo.engine.session.redis.sentinel.master=mymaster'
expect_option '-Dconvertigo.engine.session.redis.sentinel.nodes=sentinel-0:26379,sentinel-1:26379,sentinel-2:26379'
expect_option '-Dconvertigo.engine.session.redis.username=data-user'
expect_option '-Dconvertigo.engine.session.redis.password=data-test-password'
expect_option '-Dconvertigo.engine.session.redis.database=2'
expect_option '-Dconvertigo.engine.session.redis.sentinel.username=sentinel-user'
expect_option '-Dconvertigo.engine.session.redis.sentinel.password=sentinel-test-password'
expect_option '-Dconvertigo.engine.session.redis.ssl=true'
expect_option '-Dconvertigo.engine.session.redis.ssl.truststore=/tls/ca.p12'
expect_option '-Dconvertigo.engine.session.redis.ssl.keystore=/tls/client.p12'
[[ "$rendered" != *"name: sentinel-convertigo-redis"* ]]
rendered=$(helm template sentinel "$chart" "${base[@]}" --set-string 'sessionStore.redis.sentinel.nodes=sentinel-0:26379 sentinel-1:26379 sentinel-0:26379')
expect_option '-Dconvertigo.engine.session.redis.sentinel.nodes=sentinel-0:26379,sentinel-1:26379'
expect_failure --set sessionStore.redis.topology=cluster
expect_failure "${base[@]}" --set redis.enabled=true
expect_failure "${base[@]}" --set sessionStore.mode=auto
expect_failure "${base[@]}" --set sessionStore.redis.sentinel.master=
expect_failure "${base[@]}" --set-json 'sessionStore.redis.sentinel.nodes=[]'
expect_failure "${base[@]}" --set-json 'sessionStore.redis.sentinel.nodes=["host:0"]'
expect_failure "${base[@]}" --set-json 'sessionStore.redis.sentinel.nodes=["user:secret@host:26379"]'
# Embedded Redis with Sentinel
embedded=(--set redis.enabled=true --set redis.sentinel.enabled=true)
rendered=$(helm template ha "$chart" "${embedded[@]}")
expect_option 'kind: StatefulSet'
expect_option 'name: ha-convertigo-redis-headless'
expect_option 'kind: PodDisruptionBudget'
expect_option '-Dconvertigo.engine.session.redis.topology=sentinel'
expect_option '-Dconvertigo.engine.session.redis.sentinel.master=convertigo'
expect_option '-Dconvertigo.engine.session.redis.sentinel.nodes=ha-convertigo-redis-0.ha-convertigo-redis-headless.default.svc.cluster.local:26379,ha-convertigo-redis-1.ha-convertigo-redis-headless.default.svc.cluster.local:26379,ha-convertigo-redis-2.ha-convertigo-redis-headless.default.svc.cluster.local:26379'
[[ "$rendered" != *"-Dconvertigo.engine.session.redis.host="* ]]
# The single Redis is not rendered
[[ "$rendered" != *'"--appendonly"'* ]]
# Password from an existing secret: never rendered, expanded by Kubernetes
rendered=$(helm template ha "$chart" "${embedded[@]}" --set redis.auth.existingSecret=redis-auth)
expect_option 'name: redis-auth'
expect_option '-Dconvertigo.engine.session.redis.password=$(REDIS_PASSWORD)'
[[ "$rendered" != *"ChangeMe!"*"session.redis.password"* && "$rendered" != *"session.redis.password=ChangeMe!"* ]]
# Password and TLS files provided by user volumes (Vault agent)
rendered=$(helm template ha "$chart" "${embedded[@]}" --set redis.auth.passwordFile=/vault/secrets/redis-password \
  --set redis.tls.enabled=true --set redis.tls.mountPath=/vault/secrets)
expect_option 'REDIS_PASSWORD_FILE'
expect_option 'value: "/vault/secrets/redis.crt"'
expect_option '-Dconvertigo.engine.session.redis.ssl.truststore=/vault/secrets/truststore.p12'
[[ "$rendered" != *"secretName: "*"redis-tls"* ]]
[[ "$rendered" != *"session.redis.password=ChangeMe!"* ]]
# Single embedded Redis with the password in a secret
rendered=$(helm template single "$chart" --set redis.enabled=true --set redis.auth.existingSecret=redis-auth)
expect_option '- "$(REDIS_PASSWORD)"'
expect_option '-Dconvertigo.engine.session.redis.host=single-convertigo-redis'
[[ "$rendered" != *"kind: StatefulSet"* ]]
expect_failure "${embedded[@]}" --set redis.sentinel.replicas=2
expect_failure "${embedded[@]}" --set redis.sentinel.quorum=4
expect_failure "${embedded[@]}" --set 'redis.sentinel.masterName=bad name'
echo 'PASS Redis single/external/Sentinel/TLS rendering and invalid configurations'
