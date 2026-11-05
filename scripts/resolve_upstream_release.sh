#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
upstream_url="${UPSTREAM_REMOTE_URL:-https://github.com/tasks/tasks.git}"
if [ -z "${GITHUB_OUTPUT:-}" ]; then
  echo "::error::GITHUB_OUTPUT must be set."
  exit 1
fi
touch "$GITHUB_OUTPUT"

if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$upstream_url"
else
  git remote add upstream "$upstream_url"
fi

tag_listing="$(git ls-remote --tags --refs upstream)"
latest="$(
  printf '%s\n' "$tag_listing" |
    awk '$2 ~ /^refs\/tags\/[0-9]+\.[0-9]+(\.[0-9]+)?$/ { sub(/^refs\/tags\//, "", $2); print $2 }' |
    LC_ALL=C sort -V |
    tail -n 1
)"
if [ -z "$latest" ]; then
  echo "::error::No official numeric release tag was found."
  exit 1
fi

tag_ref="refs/tags/$latest"
advertised_sha="$(
  git ls-remote --exit-code upstream "$tag_ref" |
    awk -v ref="$tag_ref" '$2 == ref { print $1 }'
)"
case "$advertised_sha" in
  *[!0-9a-f]*|"")
    echo "::error::Upstream returned an invalid object ID for tag $latest."
    exit 1
    ;;
esac
if [ "${#advertised_sha}" -ne 40 ] && [ "${#advertised_sha}" -ne 64 ]; then
  echo "::error::Upstream returned an unsupported object ID length for tag $latest."
  exit 1
fi

git fetch --no-tags upstream "+$tag_ref:refs/tags/upstream-$latest"
fetched_sha="$(git rev-parse "refs/tags/upstream-$latest")"
if [ "$fetched_sha" != "$advertised_sha" ]; then
  echo "::error::Upstream tag $latest moved while it was being fetched; retry the update."
  exit 1
fi
tag_sha="$(git rev-parse "refs/tags/upstream-$latest^{commit}")"
jdk_version="$(
  git show "refs/tags/upstream-$latest:gradle/libs.versions.toml" |
    bash "$script_dir/read_jdk_version.sh"
)"

echo "Resolved upstream $latest at $tag_sha with JDK $jdk_version."
{
  echo "version=$latest"
  echo "tag_sha=$tag_sha"
  echo "tag_ref_sha=$fetched_sha"
  echo "jdk_version=$jdk_version"
} >> "$GITHUB_OUTPUT"
