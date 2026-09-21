#!/usr/bin/env python3
"""Reapply the small Windows-fork patch on top of an upstream release."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


MANAGED_PATHS = (
    "composeApp/build.gradle.kts",
    "composeApp/src/desktopMain/kotlin/main.kt",
    "composeApp/src/desktopMain/kotlin/org/tasks/analytics/PostHogReporting.kt",
    "composeApp/src/desktopMain/kotlin/org/tasks/auth/DesktopOAuthFlow.kt",
    "composeApp/src/desktopMain/kotlin/org/tasks/di/DesktopModule.kt",
)

PATCH_MARKERS = {
    "composeApp/build.gradle.kts": (
        'iconFile.set(project.file("../graphics/icon.ico"))',
    ),
    "composeApp/src/desktopMain/kotlin/main.kt": (
        "if (signalExistingInstance()) return",
        "icon = painterResource(Res.drawable.ic_round_icon)",
        "prepareDesktopUpdate(dataDir, platform())",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/analytics/PostHogReporting.kt": (
        "PostHog initialization failed",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/auth/DesktopOAuthFlow.kt": (
        "createLoopbackServerOrNull",
        "runOnReadyOrNull",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/di/DesktopModule.kt": (
        "private const val IS_GENERIC = true",
        'sku = "desktop_generic"',
    ),
}

PATCH_FILE = Path(__file__).with_name("windows-fork.patch")


def patch_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        left, separator, right = line.removeprefix("diff --git ").partition(" b/")
        if not separator or not left.startswith("a/"):
            raise ValueError(f"malformed patch header: {line}")
        left_path = left.removeprefix("a/")
        if left_path != right:
            raise ValueError(f"renames are not supported in Windows fork patch: {line}")
        paths.add(left_path)
    return paths


def validate_patch(patch_file: Path = PATCH_FILE) -> None:
    text = patch_file.read_text(encoding="utf-8")
    actual = patch_paths(text)
    expected = set(MANAGED_PATHS)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing paths: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected paths: {', '.join(extra)}")
        raise ValueError("Windows fork patch path mismatch (" + "; ".join(details) + ")")


def run_git(*args: str) -> None:
    subprocess.run(("git", *args), check=True)


def reapply(upstream_ref: str) -> None:
    validate_patch()
    run_git("checkout", upstream_ref, "--", *MANAGED_PATHS)
    run_git("apply", "--3way", "--index", PATCH_FILE.as_posix())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-ref", required=True)
    args = parser.parse_args(argv)

    try:
        reapply(args.upstream_ref)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Could not reapply Windows fork patch: {error}", file=sys.stderr)
        return 1

    print(f"Reapplied Windows fork patch on {args.upstream_ref}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
