#!/usr/bin/env bash
set -euo pipefail

normalize_release() {
  : "${VERSION:?VERSION is required}"
  tag="windows-v$VERSION"
  release="$(gh api "repos/$GITHUB_REPOSITORY/releases/tags/$tag")"
  required_suffixes=(
    "tasks-org-windows-x64-$VERSION.msi"
    "-windows-amd64.zip"
    "-windows-aarch64.zip"
    ".x64.msix"
    ".arm64.msix"
    "_amd64.deb"
    "_arm64.deb"
    "-linux-amd64.tar.gz"
    "-linux-aarch64.tar.gz"
    "-mac-amd64.zip"
    "-mac-aarch64.zip"
    "tasks-org-linux-x86_64.AppImage"
    "tasks-org-linux-x86_64.AppImage.zsync"
    "tasks-org-linux-aarch64.AppImage"
    "tasks-org-linux-aarch64.AppImage.zsync"
  )

  checksum_dir="$(mktemp -d)"
  checksums=()
  for suffix in "${required_suffixes[@]}"; do
    asset="$(
      jq -er --arg suffix "$suffix" \
        '[.assets[] | select(.name | endswith($suffix))] | if length == 1 then .[0].name else error("Expected one asset ending in " + $suffix) end' \
        <<< "$release"
    )"
    digest="$(
      jq -er --arg name "$asset" \
        '.assets[] | select(.name == $name) | .digest | select(startswith("sha256:"))' \
        <<< "$release"
    )"
    checksum="$checksum_dir/$asset.sha256"
    printf '%s  %s\n' "${digest#sha256:}" "$asset" > "$checksum"
    checksums+=("$checksum")
  done

  mapfile -t appinstaller_assets < <(
    jq -er '[.assets[] | select(.name | endswith(".appinstaller"))] | if length == 2 then .[].name else error("Expected two App Installer manifests") end' \
      <<< "$release"
  )
  arm64_manifest_count=0
  for asset in "${appinstaller_assets[@]}"; do
    if [[ "$asset" == *-arm64.appinstaller ]]; then
      arm64_manifest_count=$((arm64_manifest_count + 1))
    fi
    digest="$(
      jq -er --arg name "$asset" \
        '.assets[] | select(.name == $name) | .digest | select(startswith("sha256:"))' \
        <<< "$release"
    )"
    checksum="$checksum_dir/$asset.sha256"
    printf '%s  %s\n' "${digest#sha256:}" "$asset" > "$checksum"
    checksums+=("$checksum")
  done
  if [ "$arm64_manifest_count" -ne 1 ]; then
    echo "Expected exactly one ARM64 App Installer manifest."
    exit 1
  fi
  arm64_manifest="${appinstaller_assets[0]}"
  for asset in "${appinstaller_assets[@]}"; do
    if [[ "$asset" == *-arm64.appinstaller ]]; then
      arm64_manifest="$asset"
    fi
  done
  x64_manifest="${arm64_manifest%-arm64.appinstaller}.appinstaller"
  x64_manifest_found=false
  for asset in "${appinstaller_assets[@]}"; do
    if [ "$asset" = "$x64_manifest" ]; then
      x64_manifest_found=true
    fi
  done
  if [ "$x64_manifest_found" != true ]; then
    echo "Expected matching x64 and ARM64 App Installer manifests."
    exit 1
  fi

  gh release upload "$tag" "${checksums[@]}" --repo "$GITHUB_REPOSITORY" --clobber
  gh release edit "$tag" --repo "$GITHUB_REPOSITORY" --title "Tasks.org Desktop $VERSION" --prerelease=false --latest
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

# Validate all package and checksum assets before making the candidate visible on main.
bash scripts/verify_desktop_release_artifacts.sh release-files

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
release_files=(release-files/*)
if gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  gh release upload "$tag" "${release_files[@]}" --repo "$GITHUB_REPOSITORY" --clobber
  gh release edit "$tag" --repo "$GITHUB_REPOSITORY" --title "Tasks.org Desktop $VERSION" --prerelease=false --latest
else
  gh release create "$tag" "${release_files[@]}" \
    --repo "$GITHUB_REPOSITORY" --target "$EXPECTED_CANDIDATE" \
    --title "Tasks.org Desktop $VERSION" \
    --notes "Windows MSI, MSIX, and ZIP builds for x64 and ARM64; Linux DEB, tarball, and AppImage builds for x86_64 and ARM64; and macOS ZIP builds for Intel and Apple Silicon, based on the official Tasks.org $VERSION release. Windows MSIX installs use App Installer updates. AppImage updates use zsync. macOS packages are not notarized."
fi

git push origin --delete "$CANDIDATE_BRANCH" ||
  echo "Candidate branch was already removed."

# Issue cleanup is housekeeping; never turn a published release into a failed run.
set +e
for title in "Upstream merge conflict needs manual resolution" "Upstream update needs manual attention"; do
  gh issue list --repo "$GITHUB_REPOSITORY" --state open --search "in:title \"$title\"" --json number --jq '.[].number' |
    while IFS= read -r issue; do
      gh issue close "$issue" --repo "$GITHUB_REPOSITORY" --comment "Resolved automatically while publishing desktop release $VERSION."
    done
done
set -e
