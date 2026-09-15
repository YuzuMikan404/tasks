#!/usr/bin/env bash
set -euo pipefail

if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream https://github.com/tasks/tasks.git
else
  git remote add upstream https://github.com/tasks/tasks.git
fi
latest="$(
  git ls-remote --tags --refs upstream |
    sed 's#.*refs/tags/##' |
    grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' |
    sort -V |
    tail -n 1
)"
current="$(tr -d '[:space:]' < .github/upstream-version)"
base_sha="$(git rev-parse HEAD)"

if [ -z "$latest" ]; then
  echo "No official numeric release tag was found."
  exit 1
fi

echo "Latest official release: $latest"
echo "Current released fork version: $current"
echo "version=$latest" >> "$GITHUB_OUTPUT"
echo "base_sha=$base_sha" >> "$GITHUB_OUTPUT"

if [ "$latest" = "$current" ]; then
  msi_count="$(
    gh release view "windows-v$latest" --repo "$GITHUB_REPOSITORY" --json assets --jq '[.assets[].name | select(endswith(".msi"))] | length' 2>/dev/null || echo 0
  )"
  if [ "$msi_count" -gt 0 ]; then
    echo "Windows release windows-v$latest already has an MSI."
    echo "needs_update=false" >> "$GITHUB_OUTPUT"
    echo "candidate_sha=$base_sha" >> "$GITHUB_OUTPUT"
    echo "candidate_branch=" >> "$GITHUB_OUTPUT"
    exit 0
  fi
  echo "Windows release windows-v$latest is incomplete; rebuilding from main."
else
  fork_head="$base_sha"
  git fetch upstream "refs/tags/$latest:refs/tags/upstream-$latest"
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  python3 -m unittest discover -s scripts -p 'test_*.py'

  git merge --no-ff --no-edit "refs/tags/upstream-$latest" || true

  conflicts="$(git diff --name-only --diff-filter=U)"
  unknown_conflicts=()
  while IFS= read -r conflict; do
    [ -z "$conflict" ] && continue
    case "$conflict" in
      .github/workflows/*) ;;
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

  # Upstream Actions are never imported; this fork publishes Windows only.
  git checkout "$fork_head" -- .github/workflows
  git rm -f --ignore-unmatch .github/workflows/bundle.yml .github/workflows/release.yml .github/workflows/deploy.yml
  git add .github/workflows

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
