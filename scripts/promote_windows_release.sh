#!/usr/bin/env bash
set -euo pipefail

normalize_release() {
  : "${VERSION:?VERSION is required}"
  release="$(gh api "repos/$GITHUB_REPOSITORY/releases/tags/windows-v$VERSION")"
  msi_name="tasks-org-windows-x64-$VERSION.msi"
  checksum_name="tasks-org-windows-x64-$VERSION.sha256"
  msi_id="$(jq -r '.assets[] | select(.name | endswith(".msi")) | .id' <<< "$release" | head -n 1)"
  msi_digest="$(jq -r '.assets[] | select(.name | endswith(".msi")) | .digest' <<< "$release" | head -n 1)"

  test -n "$msi_id"
  test -n "$msi_digest"
  test "$msi_digest" != "null"
  gh api --method PATCH "repos/$GITHUB_REPOSITORY/releases/assets/$msi_id" -f "name=$msi_name" >/dev/null

  jq -r '.assets[] | select(.name | endswith(".sha256")) | .name' <<< "$release" |
    while IFS= read -r old_checksum; do
      gh release delete-asset "windows-v$VERSION" "$old_checksum" --repo "$GITHUB_REPOSITORY" --yes
    done

  printf '%s  %s\n' "${msi_digest#sha256:}" "$msi_name" > "$checksum_name"
  gh release upload "windows-v$VERSION" "$checksum_name" --repo "$GITHUB_REPOSITORY" --clobber
  gh release edit "windows-v$VERSION" --repo "$GITHUB_REPOSITORY" --title "Tasks.org Windows $VERSION" --prerelease=false --latest
}

if [ "${1:-}" = "--normalize-only" ]; then
  normalize_release
  exit 0
fi

: "${VERSION:?VERSION is required}"
: "${EXPECTED_BASE:?EXPECTED_BASE is required}"
: "${EXPECTED_CANDIDATE:?EXPECTED_CANDIDATE is required}"
: "${CANDIDATE_BRANCH:?CANDIDATE_BRANCH is required}"

candidate="$(git rev-parse HEAD)"
test "$candidate" = "$EXPECTED_CANDIDATE"
git merge-base --is-ancestor "$EXPECTED_BASE" "$candidate"

# Compare-and-swap prevents a validated candidate from overwriting newer main work.
git fetch origin main
current_main="$(git rev-parse origin/main)"
if [ "$current_main" != "$EXPECTED_BASE" ]; then
  echo "main advanced while the candidate was building; refusing stale promotion."
  exit 1
fi
if [ "$candidate" != "$current_main" ]; then
  # A normal fast-forward push rejects any race after the SHA comparison.
  git push origin "$candidate:refs/heads/main"
fi

tag="windows-v$VERSION"
msi="release-files/tasks-org-windows-x64-$VERSION.msi"
checksum="release-files/tasks-org-windows-x64-$VERSION.sha256"
test -f "$msi"
test -f "$checksum"

if gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  gh release upload "$tag" "$msi" "$checksum" --repo "$GITHUB_REPOSITORY" --clobber
  gh release edit "$tag" --repo "$GITHUB_REPOSITORY" --title "Tasks.org Windows $VERSION" --prerelease=false --latest
else
  gh release create "$tag" "$msi" "$checksum" --repo "$GITHUB_REPOSITORY" --target "$EXPECTED_CANDIDATE" --title "Tasks.org Windows $VERSION" --notes "Windows-only libre build based on the official Tasks.org $VERSION release. EteSync and self-hosted CalDAV synchronization do not require a Tasks.org subscription."
fi

git push origin --delete "$CANDIDATE_BRANCH" ||
  echo "Candidate branch was already removed."

# Issue cleanup is housekeeping; never turn a published release into a failed run.
set +e
for title in "Upstream merge conflict needs manual resolution" "Upstream update needs manual attention"; do
  gh issue list --repo "$GITHUB_REPOSITORY" --state open --search "in:title \"$title\"" --json number --jq '.[].number' |
    while IFS= read -r issue; do
      gh issue close "$issue" --repo "$GITHUB_REPOSITORY" --comment "Resolved automatically while publishing Windows release $VERSION."
    done
done
set -e
