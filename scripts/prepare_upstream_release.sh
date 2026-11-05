#!/usr/bin/env bash
set -euo pipefail

if [ -z "${GITHUB_OUTPUT:-}" ]; then
  echo "GITHUB_OUTPUT must be set."
  exit 1
fi
touch "$GITHUB_OUTPUT"

upstream_url="${UPSTREAM_REMOTE_URL:-https://github.com/tasks/tasks.git}"
if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$upstream_url"
else
  git remote add upstream "$upstream_url"
fi
if [ -n "${UPSTREAM_VERSION:-}" ]; then
  latest="$UPSTREAM_VERSION"
  if ! [[ "$latest" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "Resolved upstream version is not a numeric release tag: $latest"
    exit 1
  fi
else
  tag_listing="$(git ls-remote --tags --refs upstream)"
  latest="$(
    printf '%s\n' "$tag_listing" |
      awk '$2 ~ /^refs\/tags\/[0-9]+\.[0-9]+(\.[0-9]+)?$/ { sub(/^refs\/tags\//, "", $2); print $2 }' |
      LC_ALL=C sort -V |
      tail -n 1
  )"
fi
current="$(tr -d '[:space:]' < .github/upstream-version)"
base_sha="$(git rev-parse HEAD)"

if [ -z "$latest" ]; then
  echo "No official numeric release tag was found."
  exit 1
fi
if ! [[ "$current" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
  echo "Current upstream version marker is invalid: $current"
  exit 1
fi
newest_version="$(printf '%s\n' "$current" "$latest" | LC_ALL=C sort -V | tail -n 1)"
if [ "$newest_version" != "$latest" ]; then
  echo "Refusing to downgrade upstream from $current to $latest."
  exit 1
fi

echo "Latest official release: $latest"
echo "Current released fork version: $current"
tag_ref="refs/tags/$latest"
advertised_sha="$(
  git ls-remote --exit-code upstream "$tag_ref" |
    awk -v ref="$tag_ref" '$2 == ref { print $1 }'
)"
if [ -z "$advertised_sha" ]; then
  echo "Upstream release tag $latest disappeared before candidate preparation."
  exit 1
fi
git fetch --no-tags upstream "+$tag_ref:refs/tags/upstream-$latest"
fetched_sha="$(git rev-parse "refs/tags/upstream-$latest")"
if [ "$fetched_sha" != "$advertised_sha" ]; then
  echo "Upstream release tag $latest moved while it was being fetched."
  exit 1
fi
if [ -n "${UPSTREAM_TAG_REF_SHA:-}" ] && [ "$fetched_sha" != "$UPSTREAM_TAG_REF_SHA" ]; then
  echo "Upstream release tag $latest moved before candidate preparation."
  exit 1
fi
actual_tag_sha="$(git rev-parse "refs/tags/upstream-$latest^{commit}")"
if [ -n "${UPSTREAM_TAG_SHA:-}" ] && [ "$actual_tag_sha" != "$UPSTREAM_TAG_SHA" ]; then
  echo "Resolved upstream tag changed before candidate preparation."
  exit 1
fi

{
  echo "version=$latest"
  echo "base_sha=$base_sha"
} >> "$GITHUB_OUTPUT"

same_upstream_tag=false
if [ "$latest" = "$current" ] && git merge-base --is-ancestor "$actual_tag_sha" "$base_sha"; then
  same_upstream_tag=true
elif [ "$latest" = "$current" ]; then
  echo "The upstream tag $latest is not in the current release history; preparing it as an update."
fi

if [ "$same_upstream_tag" = true ]; then
  release_assets="$(
    gh release view "windows-v$latest" --repo "$GITHUB_REPOSITORY" --json assets --jq '.assets[].name' 2>/dev/null || true
  )"
  asset_count() {
    local suffix="$1" name count=0
    while IFS= read -r name; do
      case "$name" in
        *"$suffix") count=$((count + 1)) ;;
      esac
    done <<< "$release_assets"
    echo "$count"
  }
  required_suffixes=(
    "tasks-org-windows-x64-$latest.msi"
    "-windows-amd64.zip"
    "-windows-aarch64.zip"
    ".x64.msix"
    ".arm64.msix"
    "_amd64.deb"
    "_arm64.deb"
    "-linux-amd64.tar.gz"
    "-linux-aarch64.tar.gz"
    "tasks-org-linux-x86_64.AppImage"
    "tasks-org-linux-x86_64.AppImage.zsync"
    "tasks-org-linux-aarch64.AppImage"
    "tasks-org-linux-aarch64.AppImage.zsync"
  )
  release_complete=true
  for suffix in "${required_suffixes[@]}"; do
    count="$(asset_count "$suffix")"
    if [ "$count" -ne 1 ]; then
      echo "Release asset suffix '$suffix' is missing or ambiguous (found $count)."
      release_complete=false
    fi
  done
  appinstaller_assets=()
  while IFS= read -r name; do
    if [[ "$name" == *.appinstaller ]]; then
      appinstaller_assets+=("$name")
    fi
  done <<< "$release_assets"
  if ! bash scripts/verify_appinstaller_assets.sh "${appinstaller_assets[@]}"; then
    release_complete=false
  fi

  if [ "$release_complete" = true ]; then
    echo "Desktop release windows-v$latest already has all required Windows and Linux packages."
    echo "needs_update=false" >> "$GITHUB_OUTPUT"
    echo "candidate_sha=$base_sha" >> "$GITHUB_OUTPUT"
    echo "candidate_branch=" >> "$GITHUB_OUTPUT"
    exit 0
  fi
  echo "Desktop release windows-v$latest is incomplete; rebuilding the full platform matrix from main."
else
  fork_head="$base_sha"
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  python3 -m unittest discover -s scripts -p 'test_*.py'

  git merge --no-ff --no-edit -X theirs "refs/tags/upstream-$latest" || true

  conflicts="$(git diff --name-only --diff-filter=U)"
  unknown_conflicts=()
  while IFS= read -r conflict; do
    [ -z "$conflict" ] && continue
    case "$conflict" in
      .gitattributes) ;;
      .github/workflows/*) ;;
      .github/actions/appimage/AppRun) ;;
      .github/actions/setup-project-jdk/*) ;;
      .gitignore) ;;
      composeApp/build.gradle.kts) ;;
      composeApp/src/desktopMain/kotlin/main.kt) ;;
      composeApp/src/desktopMain/kotlin/org/tasks/analytics/PostHogReporting.kt) ;;
      composeApp/src/desktopMain/kotlin/org/tasks/auth/DesktopOAuthFlow.kt) ;;
      composeApp/src/desktopMain/kotlin/org/tasks/di/DesktopModule.kt) ;;
      kmp/src/commonMain/composeResources/values-in) ;;
      kmp/src/commonMain/composeResources/values-iw) ;;
      *) unknown_conflicts+=("$conflict") ;;
    esac
  done <<< "$conflicts"

  if [ "${#unknown_conflicts[@]}" -gt 0 ]; then
    echo "Upstream introduced conflicts outside the guarded Windows-fork patch:"
    printf '  %s\n' "${unknown_conflicts[@]}"
    git merge --abort
    exit 1
  fi

  # Upstream Actions are never imported; this fork keeps its desktop release workflow.
  # Remove the merged workflow tree first so modify/delete conflicts and files
  # that exist only upstream cannot leak into the candidate branch.
  git rm -r -f --ignore-unmatch .github/workflows
  git checkout "$fork_head" -- .gitattributes .github/actions/setup-project-jdk .github/workflows README.md WINDOWS_FORK.md

  python3 scripts/resolve_upstream_conflicts.py --upstream-ref "refs/tags/upstream-$latest"

  # These upstream aliases are symlinks. On Windows checkouts with core.symlinks=false
  # they become plain files, which Compose rejects as invalid resource directories.
  git rm -f --ignore-unmatch \
    kmp/src/commonMain/composeResources/values-in \
    kmp/src/commonMain/composeResources/values-iw

  remaining="$(git diff --name-only --diff-filter=U)"
  if [ -n "$remaining" ]; then
    echo "Unresolved conflicts remain:"
    echo "$remaining"
    git merge --abort
    exit 1
  fi

  python3 scripts/verify_windows_fork_patches.py
  ./gradlew :composeApp:desktopTest --console=plain

  printf '%s\n' "$latest" > .github/upstream-version
  git add .github/upstream-version
  if git rev-parse -q --verify MERGE_HEAD >/dev/null; then
    git commit -m "Merge upstream Tasks.org $latest"
  elif ! git diff --cached --quiet; then
    git commit -m "Track upstream Tasks.org $latest"
  fi
fi

candidate_branch="automation/upstream-$latest"
candidate_sha="$(git rev-parse HEAD)"
git push origin "HEAD:refs/heads/$candidate_branch" --force

echo "needs_update=true" >> "$GITHUB_OUTPUT"
echo "candidate_sha=$candidate_sha" >> "$GITHUB_OUTPUT"
echo "candidate_branch=$candidate_branch" >> "$GITHUB_OUTPUT"
