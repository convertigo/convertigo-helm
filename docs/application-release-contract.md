# Application release contract for the chart candidate

The application owner must confirm the next public release and its dependencies before the chart
selects it. `nocodestudio.version` is intentionally empty in this candidate and the rehearsal overlay.
No retired stable or unpublished RC is substituted. Parameterization remains available; a new No
Code workspace needs an explicit published tag, while existing workspaces are kept without a new
fetch when the version is empty. Disabling No Code installation does not require an application tag.
The Helm render rejects an enabled but unselected new No Code installation before chart resources
are applied; its default lint/publication guard also fails until selection. Synthetic tags are used
only by local unit fixtures, never as a published default.

## What the current installer actually consumes

The current URL is:

```
https://github.com/convertigo/C8oForms/releases/download/<exact-tag>/c8oforms_standalone.tar.gz
```

The installer extracts only `c8oforms_standalone/data/workspace/projects/*`, stripping four prefix
components into staging. That bundle must contain C8Oforms and all runtime libraries/integration
projects required for a clean workspace. Workspace configuration, credentials and existing project
adaptations are not imported from the archive. The installer publishes only missing project folders.

A `C8Oforms.car` release asset by itself is **not** accepted by this tar-based installation path.
It must not be renamed to the tar asset or passed to tar extraction. If the publisher chooses
CARs only, agree and test a different import/dependency-resolution path before changing the chart.
A CAR may be suitable for an engine import with its dependencies; that is a different contract
from the current pre-engine workspace bootstrap.

## Information required from the publisher

- Exact public tag and release status, target application version and minimum Convertigo core/format.
  The chart targets engine 8.4.8; do not assume that another application's RC or next branch has the
  same engine requirement. The private source is not the public download endpoint.
- Exact case-sensitive asset names, archive type, size and SHA-256. Will the standalone tar bundle
  above remain, or will only CARs/another dependency bundle be published?
- For a tar bundle: confirm its root/layout and project names. Supply a manifest of required runtime
  dependencies, their versions/hashes and whether they are bundled or fetched by references.
  Any runtime fetch must work through the agreed public/artifact access path without embedding
  private repository credentials in the chart.
- Exact supported Baserow backend/frontend versions and database prerequisites. Is the existing
  1.34.5 baseline valid, or does the new application require a 2.x line? Is a database migration
  needed, and what is its supported rollback/restore path?
- Exact required c8oforms plugin version and features/API contracts. Plugin 0.3.1's existing matrix
  (Baserow 1.34.5 and 2.4.1) is not evidence for a newer application/backend combination.
- Initial technical-administrator and normal-user provisioning with closed public signup: required
  roles/endpoints, symbols, project/library names, public URLs/paths and startup order. Confirm the
  symbols the chart writes still match the new application's libraries and account flow.
- New-installation and existing-project upgrade procedure, including reference auto-update policy
  and preservation of local adaptations/data. A new chart tag does not force-reimport old projects.

## Selection and acceptance

After publication, verify the exact public assets and their hashes/layout before setting the tag.
Keep any required packaging/installer change separate and reviewable. Select backend/plugin versions
only after owner confirmation, then rerun local rendering/upgrade tests and the authorized isolated
rehearsal: 3-replica RWX startup, project loading, account creation, a synthetic form/data source,
plugin behavior and authenticated session failover. Never infer this from an RC already running
elsewhere; no existing instance is accessed by preparing this contract.
