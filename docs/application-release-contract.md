# Application archive source contract

The public default is C8oForms `2.1.23`, downloaded from its public GitHub release. A private test
build does not need a public prerelease: select it only through an uncommitted values override.
The chart never publishes an artifact or creates a bucket.

## Default and explicit source

`nocodestudio.archiveUrl` defaults to an empty string. When empty, the unchanged source is:

```
https://github.com/convertigo/C8oForms/releases/download/<nocodestudio.version>/c8oforms_standalone.tar.gz
```

A nonempty `nocodestudio.archiveUrl` selects that complete HTTPS URL as-is, without appending the
version, a filename or a GitHub prefix. Set `nocodestudio.version` to the artifact's real identifier
for provenance; a full URL can also be used without a version. No download failure selects another
source automatically. An existing workspace is not reimported by changing these settings during a
routine chart upgrade.

## Required archive contents

The current installer extracts a **standalone tar bundle**, not `C8Oforms.car` or a dependency ZIP.
The bundle must contain all required runtime projects/libraries under:

```
c8oforms_standalone/data/workspace/projects/<project>/...
```

Four prefix components are stripped into staging. Configuration, accounts and credentials from an
archive are not imported. A full-URL override changes the source, not the format: a CAR alone cannot
be substituted for this tar, even if the URL/filename ends in .tar.gz. Agree an installer adaptation
before choosing a different format.

For a private RC, request the matching standalone bundle, checksum, build/commit and runtime
manifest from its owner; it does not need to be placed in the public GitHub release. Confirm minimum
engine, Baserow backend/frontend, plugin/API, account/symbol/route contracts and any migration plan
for that precise version. The existing backend/plugin matrix is not RC runtime qualification.

## Public-default disclosure boundary

**Any URL committed to the defaults of a public chart becomes public.** The same is true for
versioned provider examples, documentation, commits, rendered files and chart archives. Never put a
private or embargoed source there, even temporarily. Use a private values file outside the checkout,
with restricted permissions, and do not supply a signed URL through --set, shell history or process
arguments. The public example files keep archiveUrl empty. The publication preflight rejects a
nonempty archiveUrl in chart defaults without printing it; this is not a substitute for review
before any public commit or push.

A private values override is still stored in Helm release data and rendered into a namespace
ConfigMap. Treat access to those objects and to rendered manifests as private; this is not a secret
vault. The init uses a temporary private curl config rather than putting the URL into curl arguments,
and captures download output privately instead of emitting it into container logs.

A bucket/object URL being undisclosed is not access control. Its owner must supply the approved
access mechanism (for example a time-limited signed download) and account for retries after expiry.
No bucket, IAM policy, token acquisition or cloud credential is configured by this feature.

The public metadata/HEAD checker is for public releases/defaults only. Do not send a private source
to it. Verify private-artifact checksum/access out of band and keep all evidence private.
