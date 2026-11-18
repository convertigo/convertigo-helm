# Authenticated session qualification

This is a proposed protocol, not a claim of successful runtime testing. Execute only with an explicit
GO for an isolated demonstration or minikube namespace. Use that environment's context wrapper for
every operation; never substitute a shared production cluster. Preserve logs without JVM command
lines, credentials, cookies or request/response bodies. Store private evidence outside the repository.

## Establish the baseline

1. Record chart/engine build and digest, runtime UID, three Convertigo pods and their node placement,
   actual session store/topology, Sentinel master name, announced DNS names, TTL and Redis persistence.
   Verify that the Redis store is really selected (`convertigo.session.store=OK`), with no fallback
   to local Tomcat storage. Record readiness grace and connection/retry timing.
2. Use a dedicated test account and a side-effect-free test endpoint to authenticate, create an HTTP
   session and set a serializable random sentinel attribute plus an authenticated-user marker. An
   anonymous empty session is insufficient: it may never have been materialized in the shared store.
   Do not use a business transaction, admin session or real user data as the fixture.
3. Keep the cookie only in a private in-memory client or a mode-0600 cookie jar. Disable redirects that
   would create a new session silently. Fingerprint the session ID in evidence; never print it.
4. Before failure injection, force reads through each of the three Convertigo pods with the same
   cookie, correct Host/forwarded scheme and cookie path. Use an authorized local forwarding path;
   do not add a public debugging route. Record pod identity, authenticated marker, sentinel attribute,
   status, latency and session fingerprint. All three must agree before testing a failover.
5. Inspect only key names/fingerprints, type and TTL in the dedicated Redis session namespace. Never
   dump other sessions or deserialize arbitrary session payloads. Confirm the fixture is present on
   replicas before failure injection; asynchronous replication can otherwise lose the latest write.

## Separate the failure modes

Run a read-only HTTP loop every 0.5 s. Keep the cookie fixed, record timeouts/5xx and do not auto-login.
Wait for steady state and collect a baseline between events; repeat each event at least three times.
Each event needs its own authorization, target and rollback/stop condition.

| Event | What it distinguishes |
| --- | --- |
| Graceful Sentinel master switchover, no Convertigo pod stop | Discovery, reconnect, replication and session TTL |
| Stop the Convertigo pod serving the client, Redis stable | Shared session storage versus sticky/local-only state |
| Graceful Redis failover, wait for stable replication, then stop the original engine pod | Combined routing and storage behavior without conflating their timings |
| Abrupt master loss after confirmed replication (optional, separate GO) | Durability/retry limits compared with a graceful transition |

Do not change DNS, credentials, Redis flush policy, storage or client authentication during a run.
Do not FLUSHDB, delete unrelated keys or stop another namespace. Compare logical authentication and
sentinel data as well as the session fingerprint: cookie rotation on login may be intentional.

## Verdict and stop conditions

- Pass requires preserved authentication and sentinel attribute on every healthy engine pod, without
  an implicit new login. Bound and report the maximum unavailable interval and latency separately.
- A changed cookie or missing anonymous empty session alone does not establish a persistence defect.
- If the baseline already fails cross-pod reads, stop before fault injection and inspect store selection,
  serialization, cookie path/domain/secure handling, proxy routing and Redis key TTL.
- If loss appears only after Sentinel failover, correlate master promotion, replica offsets, disconnects,
  announced endpoints, store readiness and engine errors. Redis replication is asynchronous; do not
  promise zero loss under every failure. Escalate a reproducible engine/Redis defect to its owner.
- Stop immediately on unexpected workload impact or irreversible data change. Restore only the test
  configuration needed to recover service; do not restore a snapshot without a separate decision.

Record the tested versions, event, observed loss/unavailable interval, repetition count and limitations.
Remove only the test account/fixture and forwarding processes created for this qualification, using
an approved cleanup plan. Until this protocol passes, the historical chart results describe their
specific prior test and are not a guarantee for a different environment.

References: [Redis replication](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/)
and [Redis Sentinel guarantees](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/).
These describe asynchronous replication and failover limits; the test must measure the actual
configuration rather than replace those limits with a blanket zero-loss claim.
