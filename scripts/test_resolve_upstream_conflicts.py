import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from resolve_upstream_conflicts import (
    MANAGED_PATHS,
    merge_ignore_rules,
    patch_paths,
    reapply,
    validate_patch,
)


class ReapplyWindowsForkPatchTest(unittest.TestCase):
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

    def test_merge_ignore_rules_preserves_unique_rules_from_both_sides(self):
        merged = merge_ignore_rules(
            "fork-only\nshared\n",
            "upstream-only\nshared\n",
        )
        self.assertEqual(merged, "fork-only\nshared\nupstream-only\n")

    @patch("resolve_upstream_conflicts.validate_patch")
    @patch("resolve_upstream_conflicts.git_output")
    @patch("resolve_upstream_conflicts.run_git")
    def test_reapply_resolves_gitignore_conflict_before_reapplying_patch(
        self, run_git, git_output, validate_patch_mock
    ):
        git_output.side_effect = [
            "100644 1111111 2\t.gitignore\n100644 2222222 3\t.gitignore\n",
            "fork-only\nshared\n",
            "upstream-only\nshared\n",
        ]
        with TemporaryDirectory() as directory:
            previous_directory = os.getcwd()
            try:
                os.chdir(directory)
                reapply("refs/tags/upstream-16.0")
                self.assertEqual(
                    Path(".gitignore").read_text(encoding="utf-8"),
                    "fork-only\nshared\nupstream-only\n",
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
                unittest.mock.call("apply", "--3way", "--index", unittest.mock.ANY),
            ],
        )

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
    @patch("resolve_upstream_conflicts.run_git")
    def test_reapply_starts_from_upstream_then_applies_patch(self, run_git, validate_patch_mock):
        reapply("refs/tags/upstream-16.0")
        validate_patch_mock.assert_called_once_with()
        self.assertEqual(run_git.call_count, 2)
        self.assertEqual(
            run_git.call_args_list[0].args,
            ("checkout", "refs/tags/upstream-16.0", "--", *MANAGED_PATHS),
        )
        self.assertEqual(run_git.call_args_list[1].args[:3], ("apply", "--3way", "--index"))


if __name__ == "__main__":
    unittest.main()
