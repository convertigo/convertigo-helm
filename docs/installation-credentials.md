# Installation credentials

This document describes prepared bootstrap behavior, not an instruction to inspect or modify any
running instance. Use a separately approved inventory and migration plan for existing installations.

## Fresh installations

`credentials.existingSecret` is empty by default. The chart generates a retained installation Secret
and reuses it on subsequent Helm operations through `lookup`. Its independent keys are:

| Key | Consumer |
| --- | --- |
| crypto-passphrase | Engine workspace initialization, new workspaces only |
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

`crypto.existingSecret`/`passphraseKey` can select another phrase file. Component `existingSecret`
settings and key mappings can select another password source. All references are namespace-local;
they do not copy data from another namespace. Fresh renders reject inline managed-service passwords.
Legacy inline fields are ignored during explicit adoption; prepare the matching Secret and remove
obsolete inline values under the approved migration plan. Required missing/empty credentials stop initialization.
The phrase key is optional in projections only so an old workspace can retain its original setting;
a new workspace still requires it. The chart accepts no crypto JVM override alongside this workflow.

New phrase initialization is disabled until `crypto.engineCompatibilityConfirmed=true` is explicitly
selected for a qualified engine build. The current prepared image/version must not be interpreted as
proof of compatibility. Qualification includes startup, billing initialization, user roles, project
symbols and the full Baserow/NoCode account flow. No engine or account is started by the chart tests.

The bootstrap sources require Java 17+ and the matching engine libraries. The Baserow CLI/model
contract is prepared for the pinned 1.34.5 image and still needs an isolated runtime qualification.

The workspace init invokes the engine library's `Crypto2` with the explicit installation phrase,
reading input files rather than command-line secrets. It writes private Java properties and generated
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

## Existing installations

A legacy upgrade without a retained installation Secret/schema is rejected at render time unless
`credentials.adoptExisting=true` and `credentials.existingSecret` are explicitly supplied. Kept PVCs
are included in the check. The init independently checks actual workspace contents, so a client-only
render or reinstall cannot silently replace an existing passphrase with a newly generated one.

Before any adoption, obtain an explicit GO for the exact environment and use its isolated context
wrapper. The plan must preserve:

1. The current effective phrase and where it comes from. If the property is absent, retain its absence;
   do not insert a fresh phrase. A phrase supplied by a JVM override needs a separately approved,
   value-preserving configuration transition before this chart can be adopted. Keep symbols,
   administrative roles and encrypted application records intact.
2. Current database credentials, users, key mappings, Redis authentication mode and connection/routing
   settings. Supply those unchanged through selected Secrets. Do not assume new defaults equal the
   old effective values. A PostgreSQL password environment variable does not rotate a user in an
   initialized database; a credential change needs its own coordinated operation.
3. The Baserow technical account identity and staff status, its current matching password, and the
   engine's matching symbol. Bootstrap verifies an adopted account and never resets it. A discrepancy
   must be reviewed; do not clear identity markers to make initialization continue.
4. A private backup/restore plan for configuration, data and their Secrets, agreed before changes.
   Keep original values and phrase fingerprints privately; never print credentials, cookies, decoded
   symbols, JVM arguments or application documents in reports.

Adoption is not remediation or password rotation. If an account needs a new password, that separate
operation must coordinate the account and its engine symbol with the current phrase unchanged,
then validate the application. The chart's immutable bootstrap identity must be reconciled under that
same approved plan; it is not an invitation to edit markers or reset generated Secrets automatically.
Existing encrypted symbols are preserved byte for byte by the symbol bootstrap. A new phrase in a
selected Secret is ignored for an existing workspace; no value is substituted into its crypto property.

A change requiring data re-encryption must wait for supported engine migration facilities and a
separate qualification. Rollback must retain the exact phrase and credential identity needed by the
data; rolling back only an image or chart is not a credential or encryption rollback.
