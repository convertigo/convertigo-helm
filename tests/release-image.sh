#!/usr/bin/env bash
set -euo pipefail

# Run before publishing from master: the hotfix and develop branches use the convertigo-ci image of the branch,
# a release must use the official image of its appVersion.
chart="$(cd "$(dirname "$0")/../stable/convertigo" && pwd)"
version=$(sed -n 's/^appVersion: "\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$chart/Chart.yaml")
rendered=$(helm template release "$chart" --show-only templates/C8Odeployment.yaml)
[[ "$rendered" == *"image: \"convertigo:$version\""* ]] || {
  echo "The chart must use the official image convertigo:$version (image.repository: convertigo, image.tag: \"\")" >&2; exit 1;
}
[[ "$rendered" == *"imagePullPolicy: IfNotPresent"* ]] || { echo "image.pullPolicy must be IfNotPresent for a release" >&2; exit 1; }
grep -q '^  tag: ""$' "$chart/values.yaml" || { echo 'values.yaml must keep image.tag: "" (set by the Marketplace step)' >&2; exit 1; }
echo "PASS release image convertigo:$version"
