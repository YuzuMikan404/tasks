#!/usr/bin/env python3
"""Reapply the small Windows-fork patch on top of an upstream release."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


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
        "JOptionPane.YES_OPTION",
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
PATCH_MAIN_PATH = "composeApp/src/desktopMain/kotlin/main.kt"


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


def git_output(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def merge_ignore_rules(fork_content: str, upstream_content: str) -> str:
    lines = fork_content.splitlines()
    seen = set(lines)
    for line in upstream_content.splitlines():
        if line not in seen:
            lines.append(line)
            seen.add(line)
    return "\n".join(lines) + "\n"


def resolve_gitignore_conflict() -> None:
    if not git_output("ls-files", "-u", "--", ".gitignore").strip():
        return

    fork_content = git_output("show", ":2:.gitignore")
    upstream_content = git_output("show", ":3:.gitignore")
    Path(".gitignore").write_text(
        merge_ignore_rules(fork_content, upstream_content),
        encoding="utf-8",
        newline="\n",
    )
    run_git("add", "--", ".gitignore")


def resolve_patch_main_conflict() -> None:
    base_content = git_output("show", f":1:{PATCH_MAIN_PATH}")
    upstream_content = git_output("show", f":2:{PATCH_MAIN_PATH}")
    fork_content = git_output("show", f":3:{PATCH_MAIN_PATH}")
    Path(PATCH_MAIN_PATH).write_text(upstream_content, encoding="utf-8", newline="\n")

    with TemporaryDirectory() as directory:
        base_file = Path(directory, "base.kt")
        fork_file = Path(directory, "fork.kt")
        base_file.write_text(base_content, encoding="utf-8", newline="\n")
        fork_file.write_text(fork_content, encoding="utf-8", newline="\n")
        subprocess.run(
            (
                "git",
                "merge-file",
                "--ours",
                PATCH_MAIN_PATH,
                str(base_file),
                str(fork_file),
            ),
            check=True,
        )

    run_git("add", "--", PATCH_MAIN_PATH)


def apply_windows_fork_patch() -> None:
    result = subprocess.run(
        ("git", "apply", "--3way", "--index", PATCH_FILE.as_posix()),
        check=False,
    )
    if result.returncode == 0:
        return

    conflicts = git_output("diff", "--name-only", "--diff-filter=U").splitlines()
    if conflicts != [PATCH_MAIN_PATH]:
        raise subprocess.CalledProcessError(result.returncode, result.args)

    resolve_patch_main_conflict()
    remaining = git_output("diff", "--name-only", "--diff-filter=U").splitlines()
    if remaining:
        raise ValueError(f"Unresolved patch conflicts remain: {', '.join(remaining)}")


def reapply(upstream_ref: str) -> None:
    validate_patch()
    resolve_gitignore_conflict()
    run_git("checkout", upstream_ref, "--", *MANAGED_PATHS)
    apply_windows_fork_patch()


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
