import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from resolve_upstream_conflicts import (
    APPIMAGE_APPRUN_PATH,
    MANAGED_PATHS,
    PATCH_MAIN_PATH,
    SQLITE_ARM64_CHECK,
    SQLITE_ARM64_CHECK_FIXED,
    SQLITE_NATIVES_SCRIPT_PATH,
    fix_sqlite_arm64_check,
    merge_ignore_rules,
    patch_paths,
    reapply,
    resolve_appimage_apprun_conflict,
    resolve_patch_main_conflict,
    validate_patch,
)


class ReapplyWindowsForkPatchTest(unittest.TestCase):
    def test_patch_conflict_prefers_upstream_and_preserves_nonconflicting_fork_changes(self):
        with TemporaryDirectory() as directory:
            repo = Path(directory)
            target = repo / PATCH_MAIN_PATH
            target.parent.mkdir(parents=True)

            def git(*args):
                return subprocess.run(
                    ("git", *args),
                    cwd=repo,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )

            git("init", "-q", "-b", "fork")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            target.write_text(
                "registerFactories base\nkeep\nfork-point\n", encoding="utf-8"
            )
            git("add", ".")
            git("commit", "-qm", "base")
            base_commit = git("rev-parse", "HEAD").stdout.strip()

            target.write_text(
                "registerFactories fork\nkeep\nfork-only\n", encoding="utf-8"
            )
            git("commit", "-qam", "fork change")

            git("switch", "-q", "-c", "upstream", base_commit)
            target.write_text(
                "registerFactories upstream\nkeep\nfork-point\n", encoding="utf-8"
            )
            git("commit", "-qam", "upstream change")
            subprocess.run(
                ("git", "merge", "--no-edit", "fork"),
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            status = subprocess.run(
                ("git", "diff", "--name-only", "--diff-filter=U"),
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            ).stdout
            self.assertEqual(status.splitlines(), [PATCH_MAIN_PATH])

            previous_directory = os.getcwd()
            try:
                os.chdir(repo)
                resolve_patch_main_conflict()
            finally:
                os.chdir(previous_directory)

            result = target.read_text(encoding="utf-8")
            self.assertIn("registerFactories upstream", result)
            self.assertIn("fork-only", result)
            status = subprocess.run(
                ("git", "diff", "--name-only", "--diff-filter=U"),
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            ).stdout
            self.assertEqual(status, "")

    def test_merge_prefers_upstream_on_conflicting_source_changes(self):
        with TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args):
                subprocess.run(
                    ("git", *args),
                    cwd=repo,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )

            git("init", "-q", "-b", "fork")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            (repo / "app.txt").write_text("base\n", encoding="utf-8")
            git("add", "app.txt")
            git("commit", "-qm", "base")

            (repo / "app.txt").write_text("fork version\n", encoding="utf-8")
            git("commit", "-qam", "fork change")
            git("switch", "-q", "-c", "upstream", "HEAD^")
            (repo / "app.txt").write_text("upstream version\n", encoding="utf-8")
            git("commit", "-qam", "upstream change")

            git("switch", "-q", "fork")
            git("merge", "--no-edit", "-X", "theirs", "upstream")

            self.assertEqual(
                (repo / "app.txt").read_text(encoding="utf-8"),
                "upstream version\n",
            )

    def test_git_automatically_unions_conflicting_ignore_rules(self):
        with TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args):
                subprocess.run(
                    ("git", *args),
                    cwd=repo,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )

            git("init", "-q", "-b", "fork")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            attributes = Path(__file__).resolve().parent.parent / ".gitattributes"
            (repo / ".gitattributes").write_text(
                attributes.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (repo / ".gitignore").write_text("base-rule\n", encoding="utf-8")
            git("add", ".gitattributes", ".gitignore")
            git("commit", "-qm", "base")

            (repo / ".gitignore").write_text(
                "fork-rule\nshared-rule\n", encoding="utf-8"
            )
            git("commit", "-qam", "fork ignore rules")
            git("switch", "-q", "-c", "upstream", "HEAD^")
            (repo / ".gitignore").write_text(
                "upstream-rule\nshared-rule\n", encoding="utf-8"
            )
            git("commit", "-qam", "upstream ignore rules")

            git("switch", "-q", "fork")
            git("merge", "--no-edit", "upstream")

            merged_rules = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
            self.assertIn("fork-rule", merged_rules)
            self.assertIn("upstream-rule", merged_rules)
            self.assertEqual(merged_rules.count("shared-rule"), 1)

    def test_appimage_apprun_conflict_keeps_upstream_file_and_executable_mode(self):
        with TemporaryDirectory() as directory:
            repo = Path(directory)
            target = repo / APPIMAGE_APPRUN_PATH
            target.parent.mkdir(parents=True)

            def git(*args):
                return subprocess.run(
                    ("git", *args),
                    cwd=repo,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )

            git("init", "-q", "-b", "fork")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            git("config", "core.filemode", "false")
            (repo / "base.txt").write_text("base\n", encoding="utf-8")
            git("add", "base.txt")
            git("commit", "-qm", "base")
            base_commit = git("rev-parse", "HEAD").stdout.strip()

            apprun_content = '#!/bin/bash\nexec "$APPDIR/bin/tasks-org" "$@"\n'
            target.write_text(apprun_content, encoding="utf-8")
            git("add", APPIMAGE_APPRUN_PATH)
            git("update-index", "--chmod=-x", "--", APPIMAGE_APPRUN_PATH)
            git("commit", "-qm", "fork AppRun")

            git("switch", "-q", "-c", "upstream", base_commit)
            target.parent.mkdir(parents=True)
            target.write_text(apprun_content, encoding="utf-8")
            git("add", APPIMAGE_APPRUN_PATH)
            git("update-index", "--chmod=+x", "--", APPIMAGE_APPRUN_PATH)
            git("commit", "-qm", "upstream AppRun")
            git("switch", "-q", "fork")
            merge = subprocess.run(
                ("git", "merge", "--no-edit", "upstream"),
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(merge.returncode, 0)
            unmerged_entries = git(
                "ls-files", "-u", "--", APPIMAGE_APPRUN_PATH
            ).stdout.splitlines()
            self.assertEqual(len(unmerged_entries), 2)
            self.assertEqual(
                {entry.split()[0] for entry in unmerged_entries},
                {"100644", "100755"},
            )
            self.assertEqual(
                len({entry.split()[1] for entry in unmerged_entries}),
                1,
            )

            previous_directory = os.getcwd()
            try:
                os.chdir(repo)
                resolve_appimage_apprun_conflict()
            finally:
                os.chdir(previous_directory)

            self.assertEqual(
                target.read_text(encoding="utf-8"),
                apprun_content,
            )
            index_entry = git("ls-files", "--stage", "--", APPIMAGE_APPRUN_PATH).stdout
            self.assertTrue(index_entry.startswith("100755 "), index_entry)
            unresolved = git("diff", "--name-only", "--diff-filter=U").stdout
            self.assertEqual(unresolved, "")

    def test_merge_ignore_rules_preserves_unique_rules_from_both_sides(self):
        merged = merge_ignore_rules(
            "fork-only\nshared\n",
            "upstream-only\nshared\n",
        )
        self.assertEqual(merged, "fork-only\nshared\nupstream-only\n")

    @patch("resolve_upstream_conflicts.run_git")
    def test_sqlite_arm64_check_accepts_file_command_architecture_names(self, run_git):
        with TemporaryDirectory() as directory:
            path = Path(directory, SQLITE_NATIVES_SCRIPT_PATH)
            path.parent.mkdir(parents=True)
            path.write_text(SQLITE_ARM64_CHECK + "\n", encoding="utf-8")
            previous_directory = os.getcwd()
            try:
                os.chdir(directory)
                fix_sqlite_arm64_check()
                fixed = path.read_text(encoding="utf-8")
            finally:
                os.chdir(previous_directory)

            python_pattern = r"PE32\+ executable.*\(DLL\).*(Aarch64|ARM64)"
            for architecture in ("Aarch64", "ARM64"):
                output = (
                    "aarch64-windows-gnu/sqliteJni.dll: "
                    f"PE32+ executable for MS Windows 6.00 (DLL), {architecture}, 6 sections"
                )
                self.assertIsNotNone(re.search(python_pattern, output))
            self.assertIn(SQLITE_ARM64_CHECK_FIXED, fixed)
            run_git.assert_called_once_with("add", "--", SQLITE_NATIVES_SCRIPT_PATH)

    @patch("resolve_upstream_conflicts.run_git")
    def test_sqlite_arm64_check_rejects_unexpected_upstream_script(self, run_git):
        with TemporaryDirectory() as directory:
            path = Path(directory, SQLITE_NATIVES_SCRIPT_PATH)
            path.parent.mkdir(parents=True)
            path.write_text("build target with an unknown check\n", encoding="utf-8")
            previous_directory = os.getcwd()
            try:
                os.chdir(directory)
                with self.assertRaisesRegex(ValueError, "Unrecognized ARM64 check"):
                    fix_sqlite_arm64_check()
            finally:
                os.chdir(previous_directory)
        run_git.assert_not_called()

    @patch("resolve_upstream_conflicts.validate_patch")
    @patch("resolve_upstream_conflicts.apply_windows_fork_patch")
    @patch("resolve_upstream_conflicts.git_output")
    @patch("resolve_upstream_conflicts.run_git")
    def test_reapply_resolves_gitignore_conflict_before_reapplying_patch(
        self, run_git, git_output, apply_patch_mock, validate_patch_mock
    ):
        git_output.side_effect = [
            "",
            "100644 1111111 2\t.gitignore\n100644 2222222 3\t.gitignore\n",
            "fork-only\nshared\n",
            "upstream-only\nshared\n",
        ]
        with TemporaryDirectory() as directory:
            previous_directory = os.getcwd()
            try:
                os.chdir(directory)
                sqlite_script = Path(SQLITE_NATIVES_SCRIPT_PATH)
                sqlite_script.parent.mkdir(parents=True)
                sqlite_script.write_text(SQLITE_ARM64_CHECK + "\n", encoding="utf-8")
                reapply("refs/tags/upstream-16.0")
                self.assertEqual(
                    Path(".gitignore").read_text(encoding="utf-8"),
                    "fork-only\nshared\nupstream-only\n",
                )
                self.assertIn(
                    SQLITE_ARM64_CHECK_FIXED,
                    sqlite_script.read_text(encoding="utf-8"),
                )
            finally:
                os.chdir(previous_directory)

        validate_patch_mock.assert_called_once_with()
        self.assertEqual(
            run_git.call_args_list,
            [
                unittest.mock.call("add", "--", ".gitignore"),
                unittest.mock.call(
                    "checkout", "refs/tags/upstream-16.0", "--", *MANAGED_PATHS
                ),
                unittest.mock.call("add", "--", SQLITE_NATIVES_SCRIPT_PATH),
            ],
        )
        apply_patch_mock.assert_called_once_with()

    def test_parses_patch_paths(self):
        text = (
            "diff --git a/one.kt b/one.kt\n"
            "index 1111111..2222222 100644\n"
            "diff --git a/two.kt b/two.kt\n"
        )
        self.assertEqual(patch_paths(text), {"one.kt", "two.kt"})

    def test_rejects_patch_with_wrong_path_set(self):
        with TemporaryDirectory() as directory:
            patch_file = Path(directory, "fork.patch")
            patch_file.write_text("diff --git a/only.kt b/only.kt\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_patch(patch_file)

    @patch("resolve_upstream_conflicts.validate_patch")
    @patch("resolve_upstream_conflicts.apply_windows_fork_patch")
    @patch("resolve_upstream_conflicts.fix_sqlite_arm64_check")
    @patch("resolve_upstream_conflicts.run_git")
    def test_reapply_starts_from_upstream_then_applies_patch(
        self, run_git, fix_sqlite_mock, apply_patch_mock, validate_patch_mock
    ):
        reapply("refs/tags/upstream-16.0")
        validate_patch_mock.assert_called_once_with()
        self.assertEqual(run_git.call_count, 1)
        self.assertEqual(
            run_git.call_args_list[0].args,
            ("checkout", "refs/tags/upstream-16.0", "--", *MANAGED_PATHS),
        )
        fix_sqlite_mock.assert_called_once_with()
        apply_patch_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
