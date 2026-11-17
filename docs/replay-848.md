# Local 8.4.8 rehearsal kit

Prepared for an isolated OKS rehearsal. This document does not authorize access, installation,
failover or cleanup. Use only the dedicated demo wrappers after approval, never the shared OVH
context or another environment. Namespace, route, hostname and Secret identities must be reviewed.

## Candidate and values

Package the local branch into an external evidence directory; do not publish it. Raw default
render/lint is intentionally rejected until an application release is selected. For local contract
tests use `tests/candidate-848.py` with synthetic fixture tags. Only after publication and owner
confirmation, prepare a private values file with the exact tag and approved backend versions, then
use it for the following preview (replace the example path):

```sh
umask 077
application_values=/absolute/private/approved-application.yaml
evidence_dir="$(mktemp -d)"
KUBECONFIG=/dev/null helm lint stable/convertigo \
  -f providers/outscale/values.yaml -f providers/outscale/values-replay-848.yaml \
  -f "$application_values"
KUBECONFIG=/dev/null helm template rehearsal stable/convertigo \
  -f providers/outscale/values.yaml -f providers/outscale/values-replay-848.yaml \
  -f "$application_values" \
  > "$evidence_dir/rendered-private.yaml"
```

A rendered manifest contains generated credential data. Keep it private and never paste it into
an inbox, terminal transcript or ticket. These commands deliberately use no real kubeconfig.

The overlay selects an immutable standard CI beta 8.4.8 image, not aks, while the release defaults
still render `convertigo:8.4.8`. The recorded available baseline is build 30490, published 13 November;
it is **not** evidence that the later engine fixes are present. Before the Wednesday rehearsal,
select the approved CI build, verify its commit/build and digest and replace the tag/digest in the
local overlay. Record the chart commit, package hash, image digest and build in private evidence.
Do not silently use a mutable `hotfix` tag or call the old baseline qualified for newer fixes.

The hostname is reserved example data and the storage class is an example. Supply the dedicated
demo hostname/storage/route through a private local override. The base profile provides 3 replicas,
RWX workspace, persistent 3-member Sentinel, and routing through an existing Envoy Gateway. The
rehearsal overlay clears the base profile's external Secret refs to exercise generated first-install
passwords; the engine default phrase remains unchanged. Do not layer it onto retained production data.

## Application selection is pending

`nocodestudio.version` is intentionally empty in defaults and in the overlay. This candidate must
not bootstrap a new No Code workspace or be published before an exact public release is selected.
An existing workspace remains untouched when no new application release is selected. No RC tag
is guessed. The known Baserow/plugin versions are only a baseline until the application owner
confirms the new release's requirements. See [the publisher contract](application-release-contract.md).

The current initializer consumes `c8oforms_standalone.tar.gz`, not a single CAR. Confirm the actual
asset set/layout before choosing the tag; a CAR-only release requires an installer adaptation first.

## Fresh-workspace rehearsal, after approval

1. Use a new dedicated namespace/workspace, leaving the original demo and all other instances intact.
   Confirm resources/storage budget, Linux cross-node advisory locks, TLS route and rollback first.
   Do not change a user's active kube context; use only the isolated demo wrappers. Do not start a
   second concurrent installation or delete the old demo to make this test fit.
2. Install the reviewed local archive and selected CI image through those wrappers. No public chart
   publication is involved. Record aggregates: init/startup duration, 3 Ready replicas, runtime build
   and digest per pod, zero repeated restarts, completed project migration and green started/projects/
   session-store supervision. Check project/configuration owner counts, not file contents.
3. Confirm the selected published C8oForms release and its approved Baserow/plugin versions loaded, and PostgreSQL 16.15 /
   TimescaleDB 2.32.0 in the fresh database. Verify the effective extension through read-only metadata
   if present, rather than changing it to force the expected number. Check that no AwsMetering was
   installed and the route/session settings apply to every replica.
4. Retrieve initial administrator credentials only through the approved private Secret mechanism;
   do not export environment views, tokens, cookies or raw command lines. Check admin login, closed
   public signup and technical Baserow admin creation before HTTP became available. With synthetic
   data only, verify the initial user is non-staff, login works and a simple form/data-source and
   plugin aggregation give expected results. This needs the application owner's acceptance.
5. Test an interrupted init/retry only after the owner has authorized that fault on this dedicated
   namespace. Check convergence and owner counts without 0777, duplicate project publication or
   partial installation. Do not inject faults into the original demo or database.
6. Follow [the authenticated session protocol](session-failover-test.md) for cross-pod reads before
   an approved clean Sentinel promotion and engine-pod interruption. Anonymous empty-session or
   TCP-promotion success is not authenticated session persistence. Keep session identifiers private.

## Upgrade and rollback rehearsal

Use a separately approved isolated 8.4.7 fixture/copy, never someone else's running namespace.
Record private fingerprints of the original Secrets, engine properties, symbols and account state.
Perform the planned server dry-run, then the approved upgrade and verify identities unchanged,
no new account init, preserved database image/data and existing projects/adaptations. Do not rotate
the phrase or replace values to make the application start. Offline tests already exercise these
invariants on a synthetic API; they are not a substitute for runtime qualification.

Stop at the first unexplained failure. Reverting chart/image cannot undo project/database migrations;
use only the agreed restore plan and preserve failed evidence. Cleanup of the temporary namespace,
PVCs, Secrets and routes requires its own approval and exact inventory. Never run a broad uninstall,
prune, or delete storage to hide a failed rehearsal.

## Publication checkpoint

No push, tag or release is implied by version 8.4.8 in Chart.yaml. The current unselected application
release intentionally fails the publication guard. Publish only after selecting a public tag, the owner agrees,
engine/application checks are accepted, the official `convertigo:8.4.8` exists and the release-image
check passes. Provider images/scans and the separate release checklist remain prerequisites.
