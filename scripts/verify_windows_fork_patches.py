#!/usr/bin/env python3
"""Fail unless every required Windows-fork patch is present."""

from pathlib import Path
import sys

from resolve_upstream_conflicts import PATCH_MARKERS


EXTRA_MARKERS = {
    "composeApp/src/commonMain/kotlin/org/tasks/ForkPatches.kt": (
        "Platform.CALDAV, Platform.ETEBASE",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/di/ForkDesktopPatches.kt": (
        "copy(isLibre = true)",
    ),
}
REQUIRED_FILES = ("graphics/icon.ico",)


def verify(repo: Path) -> list[str]:
    errors: list[str] = []
    all_markers = {**PATCH_MARKERS, **EXTRA_MARKERS}
    for relative_path, markers in all_markers.items():
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
