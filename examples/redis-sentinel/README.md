# Redis Sentinel with mTLS for the Convertigo session store

A highly available Redis for Convertigo sessions, deployed with its own chart next to the
Convertigo chart: 1 master, 2 replicas and 3 Sentinels, every connection in mutual TLS.
Requires **Convertigo 8.4.7 or later** (`session.redis.topology=sentinel`).
The Convertigo chart can also deploy a simpler Redis Sentinel itself, with `redis.sentinel.enabled=true`
(see [Embedded Redis Sentinel](../../stable/convertigo/README.md#embedded-redis-sentinel)); this example
is for a Redis deployed and operated separately.
The `sessionStore.redis.topology` and `sessionStore.redis.sentinel.*` values come with the
Convertigo chart 8.4.7; until it is published, use the chart from this repository
(`./stable/convertigo` in the commands below).

| File | Content |
| --- | --- |
| [redis-values.yaml](redis-values.yaml) | Values for the [CloudPirates Redis chart](https://github.com/CloudPirates-io/helm-charts/tree/main/charts/redis), which uses the official `redis` image |
| [convertigo-values.yaml](convertigo-values.yaml) | Values to add to your Convertigo chart values |

Other Redis charts with Sentinel and TLS can be used with the same Convertigo settings, for example
[redis-ha](https://github.com/DandyDeveloper/charts/tree/master/charts/redis-ha) (official image,
Sentinel, TLS); it has **not** been tested with Convertigo. Whatever the chart, keep the points of
this example: TLS-only ports with client certificates, nodes and Sentinels advertised by host names
covered by the certificate, the master waiting for a failover before stopping, and a
PodDisruptionBudget.

Tested on Kubernetes 1.33 with Redis chart 0.37.2 (Redis 8.10.2) and Convertigo 8.4.7: STRICT
certificate verification, sessions shared by two Convertigo pods, rolling restart of Redis and
forced deletion of the master under load (see [Measured behavior](#measured-behavior)).

## Topology

The Redis chart runs a StatefulSet of 3 pods, each with a Redis container and a Sentinel container.
Sentinel monitors the master and promotes a replica when it fails (quorum 2). Convertigo asks the
Sentinels for the current master and follows promotions without restarting.

Nodes and Sentinels are advertised by host name
(`redis-sessions-N.redis-sessions-headless.<namespace>.svc.cluster.local`), so the certificates
can be verified in `STRICT` mode. Redis Cluster (sharding) is not supported by Convertigo.

## Prerequisites

1. **Certificates**, from your PKI:
   - a server certificate for Redis and Sentinel, with the extended key usages `serverAuth` and
     `clientAuth` (replicas and Sentinels connect to each other with it), and these subject
     alternative names: `*.redis-sessions-headless.<namespace>.svc.cluster.local`,
     `redis-sessions.<namespace>.svc.cluster.local`,
     `redis-sessions-sentinel.<namespace>.svc.cluster.local`, `localhost`;
   - a client certificate for Convertigo (`clientAuth`), signed by a CA trusted by Redis;
   - a client certificate for the probes of the Redis chart (the Convertigo one can be reused).
2. **Secrets** in the namespace (names used by the values files):

   ```sh
   kubectl create secret generic redis-sessions-tls \
     --from-file=tls.crt --from-file=tls.key --from-file=ca.crt
   kubectl create secret generic redis-sessions-probe-tls \
     --from-file=tls.crt=client.crt --from-file=tls.key=client.key
   kubectl create secret generic redis-sessions-auth \
     --from-literal=redis-password="$(openssl rand -hex 24)"
   # Java stores for Convertigo: CA truststore and client keystore (PKCS12)
   keytool -importcert -noprompt -alias redis-ca -file ca.crt \
     -keystore truststore.p12 -storetype PKCS12 -storepass changeit
   openssl pkcs12 -export -in client.crt -inkey client.key -out client.p12 \
     -name convertigo -passout pass:changeit
   kubectl create secret generic convertigo-redis-client \
     --from-file=truststore.p12 --from-file=client.p12
   ```

   Use your own store passwords, and set them in `convertigo-values.yaml`.
3. **Network**: Convertigo pods must reach every Redis pod on 6379 and every Sentinel on 26379.
   Redis pods reach each other on both ports. Convertigo pods also reach each other on 28080 for
   the administration console. A promoted replica must be reachable as soon as it is promoted.

## Install

```sh
helm install redis-sessions oci://registry-1.docker.io/cloudpirates/redis \
  --version 0.37.2 -f redis-values.yaml
kubectl rollout status statefulset/redis-sessions

helm upgrade --install convertigo ./stable/convertigo \
  -f my-values.yaml -f convertigo-values.yaml \
  --set-string sessionStore.redis.password="$(kubectl get secret redis-sessions-auth \
    -o jsonpath='{.data.redis-password}' | base64 -d)"
```

Install Redis first: a Convertigo pod started while Redis is unreachable stays not ready and
retries until Redis is reachable (see
[Redis unreachable at startup](../../stable/convertigo/README.md#redis-unreachable-at-startup)).

## Checks

```sh
# role and current master, from inside a Redis pod (mTLS with the probe certificate)
kubectl exec redis-sessions-0 -c redis -- sh -c 'export REDISCLI_AUTH="$REDIS_PASSWORD";
  C="redis-cli --tls --cacert /etc/redis/tls/ca.crt --cert /etc/redis/tls-client/tls.crt --key /etc/redis/tls-client/tls.key";
  $C role | head -1; $C -p 26379 sentinel get-master-addr-by-name sessions | head -1'
```

In each Convertigo pod log:

```text
(ConvertigoSessionManager) Redis session store: topology=sentinel, master=sessions, sentinels=rediss://...
(ConvertigoSessionManager) store=redis, provider=RedisSessionProvider, state=OK
```

`state=WAITING` means Redis was not reachable at startup: the cause is logged just before, and the
pod retries until `Redis is reachable: the session store is operational` is logged. Once logged in to the administration console, `/convertigo/admin/services/engine.ListInstances`
shows the topology, the current master address and every Convertigo instance.

With `STRICT` verification, `No subject alternative names matching IP address ...` means a node
is advertised by IP address: keep `sentinel.config.announceHostnames: true`, or as a last resort set
`sessionStore.redis.ssl.verificationMode: CA_ONLY` (chain still verified, client certificate still
required, host name not checked).

## Rolling Redis

A plain rolling restart is enough:

```sh
kubectl rollout restart statefulset/redis-sessions
kubectl rollout status statefulset/redis-sessions
```

The StatefulSet replaces one pod at a time. When the pod being stopped is the master,
`sentinel.redisShutdownWaitFailover: true` makes it wait until Sentinel has promoted a replica
before stopping. The PodDisruptionBudget keeps 2 pods during node drains. Do not force the deletion
of pods, and do not drain several nodes hosting Redis at the same time.

Change one thing at a time (Redis version, configuration, certificates) and check the roles
between two changes. Renewed certificates are only read when Redis restarts: roll Redis after
replacing `redis-sessions-tls`, and restart Convertigo after replacing `convertigo-redis-client`.

## Measured behavior

On the test cluster, with a client checking its session every 0.5 s through the Convertigo service:

| Event | Result |
| --- | --- |
| Rolling restart of the 3 Redis pods (223 s) | 486 checks, no error, no lost session; one request waited 9 s during the switch of the master |
| Forced deletion of the master (no graceful stop) | 116 checks, no error, no lost session; requests waited up to 12 s for about 30 s; Redis unavailable 16 to 23 s for Convertigo |

During a failover, requests that need Redis wait, then resume; users stay signed in. The duration
mainly depends on `sentinel.downAfterMilliseconds` (detection of an unexpected failure, 5 s here)
and is shorter for a planned switch. Redis replication is asynchronous: an unexpected failure can
lose the last session changes that were not yet replicated.
