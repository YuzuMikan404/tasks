#!/usr/bin/env python3
"""Resolve known upstream conflicts by keeping fork conflict hunks.

Git has already combined every non-conflicting upstream change into the working
file when this runs.  Keeping only the fork side of each conflict hunk therefore
preserves those upstream changes while reapplying the small Windows-fork patch.
Unknown files are deliberately rejected by the workflow before invoking this
script.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PATCH_MARKERS = {
    "composeApp/build.gradle.kts": (
        "includeAllModules = true",
        'iconFile.set(project.file("../graphics/icon.ico"))',
    ),
    "composeApp/src/commonMain/kotlin/org/tasks/App.kt": (
        "isForkEntitlementExempt()",
    ),
    "composeApp/src/commonMain/kotlin/org/tasks/di/CommonModule.kt": (
        "platformConfiguration.isLibre",
    ),
    "composeApp/src/desktopMain/kotlin/main.kt": (
        "if (signalExistingInstance()) return",
        "icon = painterResource(Res.drawable.ic_round_icon)",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/analytics/PostHogReporting.kt": (
        "PostHog initialization failed",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/auth/DesktopOAuthFlow.kt": (
        "createLoopbackServerOrNull",
        "runOnReadyOrNull",
    ),
    "composeApp/src/desktopMain/kotlin/org/tasks/di/DesktopModule.kt": (
        "firstWritableDirectory",
        ").asForkLibreBuild()",
    ),
    "kmp/src/commonMain/kotlin/org/tasks/compose/accounts/AddAccountScreen.kt": (
        "if (!hasPro && !isDesktop)",
    ),
}
ALLOWED_PATHS = frozenset(PATCH_MARKERS)


class ConflictFormatError(ValueError):
    pass


def resolve_ours(
    text: str,
    required_markers: tuple[str, ...] = (),
) -> tuple[str, int]:
    """Return *text* with standard merge hunks resolved to their HEAD side."""
    output: list[str] = []
    state = "normal"
    resolved = 0
    ours_hunk: list[str] = []
    theirs_hunk: list[str] = []

    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        if state == "normal":
            if line.startswith("<<<<<<< "):
                state = "ours"
                resolved += 1
                ours_hunk = []
                theirs_hunk = []
            elif line.startswith(("=======", ">>>>>>> ")):
                raise ConflictFormatError(f"unexpected marker at line {line_number}")
            else:
                output.append(line)
        elif state == "ours":
            if line.startswith("======="):
                state = "theirs"
            elif line.startswith(("<<<<<<< ", ">>>>>>> ")):
                raise ConflictFormatError(f"malformed ours hunk at line {line_number}")
            else:
                output.append(line)
                ours_hunk.append(line)
        else:
            if line.startswith(">>>>>>> "):
                ours_text = "".join(ours_hunk)
                theirs_text = "".join(theirs_hunk)
                has_marker = any(marker in ours_text for marker in required_markers)
                is_whitespace_only = ours_text.strip() == theirs_text.strip()
                if required_markers and not (has_marker or is_whitespace_only):
                    raise ConflictFormatError(
                        f"conflict ending at line {line_number} contains no fork patch marker"
                    )
                state = "normal"
            elif line.startswith(("<<<<<<< ", "=======")):
                raise ConflictFormatError(f"malformed theirs hunk at line {line_number}")
            else:
                theirs_hunk.append(line)

    if state != "normal":
        raise ConflictFormatError("unterminated conflict hunk")
    if resolved == 0:
        raise ConflictFormatError("no conflict markers found")
    return "".join(output), resolved


def read_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as source:
        return source.read()


def write_exact(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        destination.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)

    resolved_files: list[tuple[Path, str, int]] = []
    for raw_path in args.paths:
        normalized = Path(raw_path).as_posix()
        if normalized not in ALLOWED_PATHS:
            parser.error(f"refusing non-allowlisted path: {normalized}")
        path = Path(normalized)
        try:
            resolved_text, hunk_count = resolve_ours(
                read_exact(path),
                PATCH_MARKERS[normalized],
            )
        except (OSError, UnicodeError, ConflictFormatError) as error:
            print(f"Could not resolve {normalized}: {error}", file=sys.stderr)
            return 1
        resolved_files.append((path, resolved_text, hunk_count))

    # Parse every file before writing any, so a malformed conflict cannot leave a
    # partially resolved merge behind.
    for path, resolved_text, hunk_count in resolved_files:
        write_exact(path, resolved_text)
        print(f"Resolved {hunk_count} known fork conflict hunk(s): {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
