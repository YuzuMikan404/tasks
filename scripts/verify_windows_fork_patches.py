#!/usr/bin/env python3
"""Fail unless every required Windows-fork patch is present."""

from pathlib import Path
import sys

from resolve_upstream_conflicts import PATCH_MARKERS


REQUIRED_FILES = (
    "graphics/icon.ico",
    "composeApp/src/desktopMain/kotlin/org/tasks/auth/ForkOAuthPatches.kt",
    "composeApp/src/desktopMain/kotlin/org/tasks/update/WindowsAutoUpdater.kt",
)

REQUIRED_ABSENT_PATHS = (
    "kmp/src/commonMain/composeResources/values-in",
    "kmp/src/commonMain/composeResources/values-iw",
)

REQUIRED_MARKERS = {
    "composeApp/build.gradle.kts": (
        'upgradeUuid = "8f7f9a7e-4f73-4cb6-9f3d-37c2b3952f39"',
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/update/WindowsAutoUpdater.kt": (
        "YuzuMikan404/tasks/releases/latest",
        '"msiexec.exe"',
        "downloadVerified(installerUrl, installer, expectedHash)",
    ),
}


def verify(repo: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, markers in PATCH_MARKERS.items():
        path = repo / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"cannot read {relative_path}: {error}")
            continue
        for marker in markers:
            if marker not in text:
                errors.append(f"missing marker in {relative_path}: {marker}")
    for relative_path, markers in REQUIRED_MARKERS.items():
        path = repo / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"cannot read {relative_path}: {error}")
            continue
        for marker in markers:
            if marker not in text:
                errors.append(f"missing marker in {relative_path}: {marker}")
    for relative_path in REQUIRED_FILES:
        if not (repo / relative_path).is_file():
            errors.append(f"missing required file: {relative_path}")
    for relative_path in REQUIRED_ABSENT_PATHS:
        if (repo / relative_path).exists() or (repo / relative_path).is_symlink():
            errors.append(f"Windows-incompatible resource alias must be absent: {relative_path}")
    return errors


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    errors = verify(repo)
    if errors:
        print("Windows-fork patch verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All Windows-fork patch markers are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
