# Convertigo on OUTSCALE OKS

Use a namespace dedicated to the installation. Run commands through a context wrapper belonging
only to that environment. This guide does not select or change a kubectl context, install a controller,
or create an NFS server. The historical `nfs-deployment.yaml` is a legacy example, not the recommended
RWX setup and not a highly available storage service.

## Prerequisites

- An existing Envoy Gateway (Gateway API v1 CRDs) with an HTTPS listener and a certificate.
- A tested RWX storage class for the shared workspace. `values.yaml` uses Longhorn as an example;
  verify its NFS advisory-lock support across nodes and its failure/recovery behavior first.
- RWO storage for PostgreSQL/TimescaleDB, CouchDB, Baserow and Redis. The example explicitly sets
  all five storage-class values; `ebs-sc` is not assumed to exist on OKS. Do not change the class
  of an existing PVC during an upgrade: provision/migrate data in a separate operation.
- Secret objects in the installation namespace, supplied through your secret manager:
  `platform-admin` (`password`), `platform-redis` (`redis-password`), `platform-couchdb`
  (`username`, `password`), and `platform-database` (`postgres-password`, `billing-password`,
  `baserow-password`). Password file bytes must not include an unintended trailing newline.
  Also provide `platform-installation` (`baserow-admin-password`).
  These are example names, not pre-existing credentials. The engine default phrase is retained;
  no phrase is generated. A custom phrase requires `crypto.passphrase` or `crypto.existingSecret`
  explicitly and a qualified engine with `crypto.engineCompatibilityConfirmed=true`. This example
  does not opt in to a custom phrase.

Render and lint locally before any installation, using `values.yaml`. Replace the example hostname,
classes and Secret names. The chart metadata remains on the current published engine version until
its release is approved. There is no implicit dependency on AWS instance metadata: AWS Marketplace
project installation is opt-in. On a previously initialized workspace, separately review/remove an
already-installed `AwsMetering` project; the chart preserves existing projects and does not delete it.

## Startup and workspace installation

The `workspace-setup` init container serializes installation with an advisory lock on the RWX volume.
It downloads/extracts into staging, publishes only complete missing project directories, repairs
ownership and writes a completion marker last. Existing projects and their local changes are kept.
An interrupted legacy project that is itself incomplete requires operator inspection; a chart upgrade
must not silently overwrite it. Existing BaserowIntegration directories do not skip permission repair.

By default this init runs as root and the engine keeps its normal runtime identity. On a root-squashed
or restricted volume, pre-provision ownership and set `workspaceOwnershipInit.enabled=false`; the init
then runs with the runtime UID/GID and cannot repair files owned by somebody else. Confirm this mode
on your storage, not by broadening permissions. Other init containers run after workspace setup.

The startup probe gates liveness/readiness while projects load or migrate, for up to 10 minutes after
Tomcat starts. Download/install time belongs to the init phase and is not charged to that probe.
The default deployment progress deadline is 30 minutes. An init lock timeout or permission error is
reported as a failed init, rather than starting an engine on a partially prepared workspace.

## Route through an existing Gateway

A chart-native Gateway feature is not introduced in this patch. Attach the following HTTPRoute to an
existing Gateway, after substituting the release/namespace, gateway name and permitted listener.
The Gateway owner must allow a route from this namespace. The controller and its TLS Secret remain
separate infrastructure. For the example release `demo`, the chart backend names are shown below.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: demo
  namespace: demo
spec:
  parentRefs:
    - name: public-gateway
      namespace: gateway-system
      sectionName: https
  hostnames: [demo.example.com]
  rules:
    - matches:
        - path: {type: PathPrefix, value: /convertigo}
      backendRefs:
        - name: demo-convertigo
          port: 28080
    - matches:
        - path: {type: PathPrefix, value: /}
      backendRefs:
        - name: demo-convertigo-br
          port: 80
```

With Redis session storage, do not rely on sticky routing to demonstrate failover. Validate
cross-pod reads with an authenticated session and serializable data before any disruption. See
`docs/session-failover-test.md`. Successful TCP promotion alone is not proof of session persistence.

A load balancer operating in VIP mode without PROXY protocol may hide the client address.
Forwarding headers cannot reconstruct an address the load balancer never supplied. Choose the
supported LBU/Gateway forwarding mode with the network owner, trust headers only from the expected
upstream and verify it with a request from a known external address. This is not fixed by a chart
annotation or by accepting arbitrary incoming X-Forwarded-For headers.

## Upgrade and rollback

Preserve the workspace, database backups and previous values before the approved upgrade. Check
that old pods are no longer installing projects before replacing the legacy installer. Validate a
cold RWX start, permission repair and interruption/retry on an isolated environment first. Do not
run a failover or kill production pods merely to validate this guide. Revert to the previous chart
and values if required; do not restore or delete persistent data automatically. Reverting a chart
does not undo database/project migrations or a credential change: plan those steps separately.


Before upgrading an older installation, follow `../../docs/installation-credentials.md`. Normal
upgrades retain established Secrets and values, do not require adoption, and never initialize
accounts or change the effective passphrase. Review any later production credential migration
individually. Never generate replacement passwords for existing PVCs during a routine upgrade.
