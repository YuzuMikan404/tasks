#!/usr/bin/env bash
set -euo pipefail

release_dir="${1:-release-files}"

required_patterns=(
  "tasks-org-windows-x64-*.msi:1"
  "tasks-org-*.x64.msix:1"
  "tasks-org-*.arm64.msix:1"
  "*-windows-amd64.zip:1"
  "*-windows-aarch64.zip:1"
  "*.appinstaller:2"
  "*_amd64.deb:1"
  "*_arm64.deb:1"
  "*-linux-amd64.tar.gz:1"
  "*-linux-aarch64.tar.gz:1"
  "tasks-org-linux-x86_64.AppImage:1"
  "tasks-org-linux-x86_64.AppImage.zsync:1"
  "tasks-org-linux-aarch64.AppImage:1"
  "tasks-org-linux-aarch64.AppImage.zsync:1"
)

for required in "${required_patterns[@]}"; do
  pattern="${required%:*}"
  expected_count="${required##*:}"
  mapfile -t matches < <(find "$release_dir" -type f -name "$pattern" -print)
  if [ "${#matches[@]}" -ne "$expected_count" ]; then
    echo "::error::Expected $expected_count release asset(s) matching $pattern; found ${#matches[@]}."
    exit 1
  fi
  for asset in "${matches[@]}"; do
    checksum="$asset.sha256"
    if [ ! -f "$checksum" ]; then
      echo "::error::Missing checksum for $(basename "$asset")."
      exit 1
    fi
    (cd "$(dirname "$checksum")" && sha256sum --check "$(basename "$checksum")")
  done
done

mapfile -t mac_amd64_assets < <(find "$release_dir" -type f -name "*-mac-amd64.zip" -print)
mapfile -t mac_aarch64_assets < <(find "$release_dir" -type f -name "*-mac-aarch64.zip" -print)
if [ "${#mac_amd64_assets[@]}" -ne "${#mac_aarch64_assets[@]}" ] ||
  [ "${#mac_amd64_assets[@]}" -gt 1 ]; then
  echo "::error::macOS release assets must include exactly one asset per architecture or be omitted."
  exit 1
fi
for asset in "${mac_amd64_assets[@]}" "${mac_aarch64_assets[@]}"; do
  checksum="$asset.sha256"
  if [ ! -f "$checksum" ]; then
    echo "::error::Missing checksum for $(basename "$asset")."
    exit 1
  fi
  (cd "$(dirname "$checksum")" && sha256sum --check "$(basename "$checksum")")
done

mapfile -t appinstaller_assets < <(find "$release_dir" -type f -name "*.appinstaller" -print)
arm64_appinstallers=()
x64_appinstallers=()
for asset in "${appinstaller_assets[@]}"; do
  name="$(basename "$asset")"
  if [[ "$name" == *-arm64.appinstaller ]]; then
    arm64_appinstallers+=("$name")
  else
    x64_appinstallers+=("$name")
  fi
done
if [ "${#arm64_appinstallers[@]}" -ne 1 ]; then
  echo "::error::Missing ARM64 App Installer manifest."
  exit 1
fi
if [ "${#x64_appinstallers[@]}" -ne 1 ]; then
  echo "::error::Missing x64 App Installer manifest."
  exit 1
fi
expected_x64_name="${arm64_appinstallers[0]%-arm64.appinstaller}.appinstaller"
if [ "${x64_appinstallers[0]}" != "$expected_x64_name" ]; then
  echo "::error::x64 and ARM64 App Installer manifests do not belong to the same application."
  exit 1
fi

echo "All required desktop assets and SHA-256 checksums are present and valid."
