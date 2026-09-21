#!/usr/bin/env bash
set -euo pipefail

normalize_release() {
  : "${VERSION:?VERSION is required}"
  release="$(gh api "repos/$GITHUB_REPOSITORY/releases/tags/windows-v$VERSION")"
  msi_name="tasks-org-windows-x64-$VERSION.msi"
  deb_name="tasks-org-linux-x64-$VERSION.deb"
  msi_id="$(jq -r '.assets[] | select(.name | endswith(".msi")) | .id' <<< "$release" | head -n 1)"
  msi_digest="$(jq -r '.assets[] | select(.name | endswith(".msi")) | .digest' <<< "$release" | head -n 1)"
  deb_id="$(jq -r '.assets[] | select(.name | endswith(".deb")) | .id' <<< "$release" | head -n 1)"
  deb_digest="$(jq -r '.assets[] | select(.name | endswith(".deb")) | .digest' <<< "$release" | head -n 1)"

  test -n "$msi_id"
  test -n "$msi_digest"
  test "$msi_digest" != "null"
  test -n "$deb_id"
  test -n "$deb_digest"
  test "$deb_digest" != "null"
  gh api --method PATCH "repos/$GITHUB_REPOSITORY/releases/assets/$msi_id" -f "name=$msi_name" >/dev/null
  gh api --method PATCH "repos/$GITHUB_REPOSITORY/releases/assets/$deb_id" -f "name=$deb_name" >/dev/null

  jq -r '.assets[] | select(.name | endswith(".sha256")) | .name' <<< "$release" |
    while IFS= read -r old_checksum; do
      gh release delete-asset "windows-v$VERSION" "$old_checksum" --repo "$GITHUB_REPOSITORY" --yes
    done

  printf '%s  %s\n' "${msi_digest#sha256:}" "$msi_name" > "tasks-org-windows-x64-$VERSION.sha256"
  printf '%s  %s\n' "${deb_digest#sha256:}" "$deb_name" > "tasks-org-linux-x64-$VERSION.sha256"
  gh release upload "windows-v$VERSION" \
    "tasks-org-windows-x64-$VERSION.sha256" \
    "tasks-org-linux-x64-$VERSION.sha256" \
    --repo "$GITHUB_REPOSITORY" --clobber
  gh release edit "windows-v$VERSION" --repo "$GITHUB_REPOSITORY" --title "Tasks.org Desktop $VERSION" --prerelease=false --latest
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
  echo "main advanced while the candidate was building; candidate is superseded, skipping publication."

  # Only remove the candidate branch when it still points at this run's exact
  # candidate. This avoids deleting a branch that another actor refreshed.
  remote_candidate="$(git ls-remote origin "refs/heads/$CANDIDATE_BRANCH" | awk '{print $1}' || true)"
  if [ "$remote_candidate" = "$EXPECTED_CANDIDATE" ]; then
    git push origin --delete "$CANDIDATE_BRANCH" ||
      echo "Superseded candidate branch was already removed."
  fi
  exit 0
fi
if [ "$candidate" != "$current_main" ]; then
  # A normal fast-forward push rejects any race after the SHA comparison.
  git push origin "$candidate:refs/heads/main"
fi

tag="windows-v$VERSION"
msi="release-files/tasks-org-windows-x64-$VERSION.msi"
checksum="release-files/tasks-org-windows-x64-$VERSION.sha256"
deb="release-files/tasks-org-linux-x64-$VERSION.deb"
deb_checksum="release-files/tasks-org-linux-x64-$VERSION.sha256"
test -f "$msi"
test -f "$checksum"
test -f "$deb"
test -f "$deb_checksum"

if gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  gh release upload "$tag" "$msi" "$checksum" "$deb" "$deb_checksum" --repo "$GITHUB_REPOSITORY" --clobber
  gh release edit "$tag" --repo "$GITHUB_REPOSITORY" --title "Tasks.org Desktop $VERSION" --prerelease=false --latest
else
  gh release create "$tag" "$msi" "$checksum" "$deb" "$deb_checksum" --repo "$GITHUB_REPOSITORY" --target "$EXPECTED_CANDIDATE" --title "Tasks.org Desktop $VERSION" --notes "Windows and Linux desktop builds based on the official Tasks.org $VERSION release, with the desktop generic entitlement enabled."
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
