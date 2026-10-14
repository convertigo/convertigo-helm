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
  [[ "$output" == *"sessionStore"* || "$output" == *"Sentinel requires"* ]] || {
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
echo 'PASS Redis single/external/Sentinel/TLS rendering and invalid configurations'
