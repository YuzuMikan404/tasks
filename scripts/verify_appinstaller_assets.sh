#!/usr/bin/env bash
set -euo pipefail

arm64_appinstallers=()
x64_appinstallers=()

for asset in "$@"; do
  name="${asset##*/}"
  case "$name" in
    *-arm64.appinstaller)
      arm64_appinstallers+=("$name")
      ;;
    *.appinstaller)
      x64_appinstallers+=("$name")
      ;;
    *)
      echo "Unexpected App Installer asset name: $name"
      exit 1
      ;;
  esac
done

if [ "${#arm64_appinstallers[@]}" -ne 1 ] || [ "${#x64_appinstallers[@]}" -ne 1 ]; then
  echo "Expected exactly one x64 and one ARM64 App Installer manifest."
  exit 1
fi

expected_x64_name="${arm64_appinstallers[0]%-arm64.appinstaller}.appinstaller"
if [ "${x64_appinstallers[0]}" != "$expected_x64_name" ]; then
  echo "Expected matching x64 and ARM64 App Installer manifests."
  exit 1
fi
