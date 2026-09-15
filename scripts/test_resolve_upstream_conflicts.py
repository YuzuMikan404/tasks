from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from resolve_upstream_conflicts import MANAGED_PATHS, patch_paths, reapply, validate_patch


class ReapplyWindowsForkPatchTest(unittest.TestCase):
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
