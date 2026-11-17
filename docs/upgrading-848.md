# Preparing an 8.4.8 upgrade

This is a local release candidate. Publication, installation, project removal and database maintenance
are separate actions requiring the environment owner's approval. No action below is automatic.

## Versions and existing data

Fresh workspaces use C8oForms 2.1.23 (the stable line), Baserow 1.34.5 and the embedded c8oforms
plugin 0.3.1. The plugin's archive/hash and its tested 1.34.5 combination are unchanged. A C8oForms
2.2 beta or a Baserow major upgrade is not selected by this patch. Confirm the application owner's
choice and qualify the complete first-account/form/data-source flow before release.

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

The project installer publishes only missing directories. Bumping `nocodestudio.version` selects
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
