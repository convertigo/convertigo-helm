# Application release contract for the chart candidate

The candidate selects `nocodestudio.version: "2.2-rc"` as the target public prerelease. The publisher
must create this exact public tag (or agree another exact spelling and update the value), with a
release marked as a prerelease and assets from the selected RC build. Do not just relabel an older
beta. The final public release will replace this value when ready and approved.

The separate fresh-rehearsal fallback is `2.2.0-beta349.1` through
`providers/outscale/values-replay-848-fallback.yaml`. No installer automatically switches to it on
HTTP errors, and it must not downgrade an existing RC workspace. A chart upgrade keeps existing
application projects and identities rather than reimporting the new default tag.

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

## Public prerelease assets to publish

Under `https://github.com/convertigo/C8oForms/releases/tag/2.2-rc`, publish these exact names from
the same RC build, matching the public packaging convention:

| Asset | Chart use / required content |
| --- | --- |
| `c8oforms_standalone.tar.gz` | Required by the current chart. Keep the root/layout above and include all runtime projects/libraries for a fresh workspace. |
| `C8Oforms.car` | Project import delivery; not the current pre-engine tar bootstrap. |
| `no_code_studio_and_dependencies.zip` | Complete project/dependency delivery for the corresponding release; not read by the current bootstrap. |

Attach sizes and SHA-256 values plus a build/commit and dependency manifest. The tar is the
minimum needed by this chart; the other two preserve the expected release delivery set. A release
containing only the CAR or ZIP cannot satisfy the chart's current download/extraction path.
`tests/application-release-assets.py --version <tag>` checks public metadata and HEAD availability
of all three; the publication workflow reads the selected tag via `--values` and fails if the
public assets are missing. This does not prove contents or runtime compatibility. Recheck bundle layout/hash
and qualify the application before rollout. Public metadata is read without credentials.

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
