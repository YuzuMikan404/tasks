#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "Usage: read_jdk_version.sh [version-catalog]" >&2
  exit 2
fi

input="${1:-/dev/stdin}"
awk '
  /^[[:space:]]*jdk[[:space:]]*=/ {
    count++
    line = $0
    if (line !~ /^[[:space:]]*jdk[[:space:]]*=[[:space:]]*("[0-9]+"|[0-9]+)[[:space:]]*(#.*)?$/) {
      invalid = 1
      next
    }

    sub(/^[^=]*=[[:space:]]*/, "", line)
    sub(/[[:space:]]*(#.*)?$/, "", line)
    gsub(/^"|"$/, "", line)
    if (line !~ /^[1-9][0-9]*$/) {
      invalid = 1
      next
    }
    version = line
  }

  END {
    if (count != 1 || invalid) {
      print "Expected exactly one positive numeric jdk version in gradle/libs.versions.toml." > "/dev/stderr"
      exit 1
    }
    print version
  }
' "$input"
