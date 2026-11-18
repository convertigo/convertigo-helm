# Installation credentials

This document describes prepared bootstrap behavior, not an instruction to inspect or modify any
running instance. Use a separately approved inventory and migration plan for existing installations.

## Fresh installations

`credentials.existingSecret` is empty by default. The chart generates a retained installation Secret
and reuses it on subsequent Helm operations through `lookup`. Its six independent password keys are:

| Key | Consumer |
| --- | --- |
| baserow-admin-password | Baserow account init and encrypted engine symbol |
| postgres-password | PostgreSQL initialization and engine billing connection |
| billing-password | Billing user creation and encrypted billing symbol |
| baserow-database-password | Baserow PostgreSQL user and backend |
| couchdb-password | CouchDB and engine FullSync |
| redis-password | Authenticated embedded Redis and engine session store |

Each generated value is 64 alphanumeric characters. The separate engine administrator Secret keeps
its own lifecycle described in the chart README. Generated Secrets are kept at uninstall; preserve
them with the workspace and database backups. A reinstall onto retained data is not a fresh identity.
For offline/GitOps deployments, provide explicit stable Secrets rather than relying on client-side
random rendering or unavailable `lookup` results.

No encryption phrase is generated, including on a fresh installation. With default values the
workspace has no crypto.passphrase property and the engine keeps its own default.

A custom phrase is opt-in only: provide `crypto.passphrase` OR `crypto.existingSecret` with
`crypto.passphraseKey` (default `crypto-passphrase`). Prefer a Secret in production. An explicitly
supplied value is stored in a separate retained `<fullname>-crypto` Secret; it is never randomly
generated. An external Secret is referenced without copying its data. When both settings are supplied,
the explicit Secret takes precedence. A phrase present only in `credentials.existingSecret` does not
select custom mode: use the crypto settings explicitly. The default path mounts no phrase file.

Component `existingSecret` settings and key mappings can select another password source. All references are namespace-local;
they do not copy data from another namespace. Inline fields remain available for compatibility.
Historical inline password fields remain accepted. On a fresh installation, explicitly supplied
values populate the installation Secret instead of being replaced by random ones. Upgrades retain
established values and references; a missing generated Secret is never created during an upgrade.
The chart does not require an adoption flag or a private inventory to perform a normal upgrade.
Required credentials for a new initialization must be present; no old workspace is initialized.

Only an explicitly selected custom phrase is gated by `crypto.engineCompatibilityConfirmed=true`
for a qualified engine build. This flag alone does not opt into custom mode or generate any phrase.
Default-phrase installations do not require this flag. The current prepared image/version is not
proof of compatibility with a custom phrase. Qualification includes startup, billing initialization, user roles, project
symbols and the full Baserow/NoCode account flow. No engine or account is started by the chart tests.

The bootstrap sources require Java 17+ and the matching engine libraries. The Baserow CLI/model
contract is prepared for the pinned 1.34.5 image and still needs an isolated runtime qualification.

The workspace init invokes the engine library's `Crypto2` using either its default phrase or the
explicitly selected phrase read from a mounted file, never a command-line secret. Default metadata
is read from the selected engine library without initializing the engine; its value is not copied into
the chart, a generated Secret, or engine.properties. It writes private Java properties and generated
symbol values atomically. No fixed symbol ciphertext is included in the chart. Empty placeholders
are omitted and project defaults apply; empty `.secret` properties must not be fabricated manually.
The init's identity marker rejects a changed phrase or credential bundle. There is no automatic
passphrase rotation, decryption/re-encryption of old symbols, or migration of user records.

The initial Baserow staff account is provisioned before the HTTP container starts. The one-off
backend commands use a temporary loopback-only Redis cache in the init container, stopped before
the main service starts; this is separate from the engine session store. Default signup
and invitation signup are closed. An explicitly requested public-signup policy is a deployment
choice, not a prerequisite for the server-side account integration. Bootstrap does not reset any
existing password, activate another user or grant staff to an unrelated account. Interrupted fresh
creation can resume with the same identity. An unexpected existing account/credential stops startup.

## Existing installations and ordinary Helm upgrades

Generation is installation-only. On upgrades, `lookup` reuses the complete data of already-generated
installation and administrator Secrets, including additional keys. No random fallback fills a missing
Secret or key during an upgrade. Explicit component Secret references remain in use. Historical
8.4.7 values are accepted without `credentials.adoptExisting`; that field is retained only as an inert
compatibility setting. No account initialization or Baserow signup-policy write runs on upgrade.

Existing workloads are looked up to preserve their established account/connection environment
entries and Secret references, including credentials that came from old chart
defaults rather than saved user values. When an offline render cannot find those resources, it uses
the supplied historical values/references and generates nothing. Use a server dry-run with the proper
release namespace for a representative upgrade preview. A client-only preview is not proof of the
live values. The legacy environment remains in its original form; improving that exposure is a
separate, explicitly approved migration. The historical JAVA_OPTS entry is preserved as a whole because it can embed credentials. Other
settings such as JXMX and plugin options still evolve normally. A separate approved change is needed
to replace an existing JAVA_OPTS entry without changing its credential identity.

Workspace initialization skips all credential, administrator, crypto and symbol writes for upgrades
or retained workspaces. Existing engine properties, global symbols and user-role records remain
untouched. This includes an absent crypto property (the engine's established default) and existing
JVM overrides. The chart neither re-encrypts data nor resets passwords. Changes to Secret contents
or new credential values supplied during an upgrade do not authorize an account/password change.
Keep the matching Secret data with persistent storage; restore a missing managed Secret from its
backup rather than generating a replacement identity.

After an upgrade the chart's safer project installer and probes may be used, but the credential
workflow does not convert an existing production to the new-installation scheme. Productions will
be reviewed individually. Any future account/credential migration needs its own approved inventory,
consistent account and application settings, backups, rollback and functional qualification. Never
change crypto.passphrase for retained data; the engine does not re-encrypt it. PostgreSQL initialization
variables do not rotate users in an existing database.

Rollback preserves the exact phrase and credential identity needed by the data. Rolling back only
an image or chart is not a credential or encryption rollback. Never clear identity markers, delete
kept Secrets, reset an account or restore data automatically to make a routine upgrade proceed.

## Local upgrade regression test

Run `python3 tests/upgrade-credentials.py`. It performs real `helm upgrade --dry-run=server` commands
(ordinary and --reuse-values) against a GET-only Kubernetes API fixture bound to loopback, initialized from the published 8.4.7
chart. It never uses a real cluster configuration or starts an engine. Cases include historical
values with no credential Secret, existing CouchDB/Redis Secrets, minimal saved credential values,
and Redis with and without AUTH. Existing environments/references are compared exactly; generated
Secrets are reused byte for byte, including extra keys and an explicitly supplied custom-phrase
Secret; unrelated JXMX changes remain effective. The rendered installer is exercised on
synthetic retained workspace files, checking unchanged contents and modes and no credential CLI call.
This tests upgrade rendering and workspace credential preservation, not live production availability.
