#!/usr/bin/env bash
set -euo pipefail

title="Upstream update needs manual attention"
run_url="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
body="$(printf 'Automatic desktop update %s failed.\n\nprepare: %s\nmaintenance: %s\nSQLite natives: %s\ndesktop jars: %s\nWindows MSI: %s\nWindows MSIX/ZIP: %s\nLinux matrix: %s\nAppImages: %s\npublish: %s\n\nRun: %s\n' \
  "${VERSION:-unknown}" "$PREPARE_RESULT" "$MAINTENANCE_RESULT" "$SQLITE_NATIVES_RESULT" "$DESKTOP_JAR_RESULT" \
  "$WINDOWS_RESULT" "$WINDOWS_BUNDLE_RESULT" "$LINUX_RESULT" "$APPIMAGE_RESULT" "$PUBLISH_RESULT" "$run_url")"
existing="$(gh issue list --repo "$GITHUB_REPOSITORY" --state open --search "in:title \"$title\"" --json number --jq '.[0].number' || true)"

if [ -n "$existing" ] && [ "$existing" != "null" ]; then
  gh issue comment "$existing" --repo "$GITHUB_REPOSITORY" --body "$body"
else
  gh issue create --repo "$GITHUB_REPOSITORY" --title "$title" --body "$body"
fi
