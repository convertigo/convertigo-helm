# Preparing an 8.4.8 upgrade

This is a local release candidate. Publication, installation, project removal and database maintenance
are separate actions requiring the environment owner's approval. No action below is automatic.

## Versions and existing data

The public default remains C8oForms 2.1.23. A private RC is selected only via an uncommitted
`nocodestudio.archiveUrl` override to a complete compatible tar; it need not be published publicly.
The historical rehearsal-only beta349.1 fallback remains a separate explicit overlay, not an
automatic downgrade. See [the source contract](application-release-contract.md).

Baserow 1.34.5 and plugin 0.3.1 remain the existing baseline, not a compatibility claim for the next
application release. Their known plugin matrix does not prove that a newer C8oForms application can
use that backend. Confirm exact Baserow/plugin versions and qualify account/form/data-source flows
before selecting the final combination. No Baserow major upgrade is made implicitly.

The fresh database image is pinned to `timescale/timescaledb:2.32.0-pg16`, PostgreSQL major 16.
At preparation time the registry gives it the same index digest as `latest-pg16`; its amd64 image
reports PostgreSQL 16.15. TimescaleDB's release compatibility ceiling for this version is PostgreSQL
16.15. Do not independently upgrade PostgreSQL beyond that ceiling. This is a source/metadata
compatibility check, not a database restore or migration qualification.

A new database default does not authorize upgrading a retained database. During a server-side
upgrade the existing Timescale Deployment image and connection environment are preserved by lookup.
A database-image/extension change needs its own approved maintenance, backup, supported upgrade
path and restore test. Setting the chart's new default alone does not replace the running database
image. An offline preview cannot see the existing image; use a server dry-run against the correct
namespace for a representative preview. Never infer the installed extension version from an image
tag, run ALTER EXTENSION automatically, or switch a retained PostgreSQL data directory across majors.

The project installer publishes only missing directories during new-workspace initialization;
a routine chart upgrade does not import a new application into a retained workspace. Bumping `nocodestudio.version` selects
an archive for a new workspace; it does not replace an existing C8oForms project or local adaptations.
Review any application upgrade separately. Existing Secrets, passwords, symbols and effective crypto
phrase stay unchanged. Fresh passwords are generated/provided; a custom phrase stays explicit opt-in.

## AwsMetering installed on the wrong provider

`awsMarketplace.enabled=false` prevents future installation. It does **not** unload or delete an
already installed `AwsMetering`, and a reachable metadata endpoint does not identify an AWS purchase.
An actual AWS Marketplace installation must retain its required metering under its owner's policy.

For an installation where the owner confirms the project was installed in error:

1. Obtain a separate removal approval. Identify references and scheduled tasks that target only
   AwsMetering; record their names/state privately without exporting credentials. Agree a short
   maintenance window and a rollback before touching the project.
2. Export the exact project as a private CAR backup and preserve its current references/schedules
   outside the workspace/install path. Do not store this archive in a public repository or report.
3. Keep the chart option false. Disable the specific triggers and remove any approved auto-import
   reference so they cannot recreate or invoke the project. Do not alter billing databases or other
   projects as part of this operation.
4. Use the authenticated Projects administration to delete **AwsMetering only**. The engine's
   `projects.Delete` service removes the project and its CAR, clears its schema cache and emits the
   shared-workspace deletion marker; this is why a backup outside that path is necessary. Do not
   substitute a blanket workspace deletion or an uncoordinated filesystem rm command.
5. Verify on every replica that the project is unloaded and its specific schedules no longer run;
   then check supervision, the application and absence of new metering calls after a restart already
   authorized for that environment. If propagation is uncertain, stop and review rather than force
   a global restart or remove more data.

Rollback, if approved: reimport the saved CAR and restore only its prior references/schedule states,
then verify each replica. Keep chart installation disabled on a non-AWS deployment; re-enabling it
would fetch upstream content instead of restoring the captured version. No cleanup hook performs
this procedure, and no data/Secret/database is deleted by this chart.
