from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from resolve_upstream_conflicts import ConflictFormatError, main, resolve_ours


class ResolveOursTest(unittest.TestCase):
    def test_keeps_ours_and_non_conflicting_lines(self):
        merged = (
            "upstream change before\n"
            "<<<<<<< HEAD\n"
            "fork patch\n"
            "=======\n"
            "new upstream implementation\n"
            ">>>>>>> upstream-16.0\n"
            "upstream change after\n"
        )
        resolved, count = resolve_ours(merged)
        self.assertEqual(
            resolved,
            "upstream change before\nfork patch\nupstream change after\n",
        )
        self.assertEqual(count, 1)

    def test_resolves_multiple_hunks(self):
        merged = (
            "<<<<<<< HEAD\na\n=======\nx\n>>>>>>> upstream\n"
            "middle\n"
            "<<<<<<< HEAD\nb\n=======\ny\n>>>>>>> upstream\n"
        )
        self.assertEqual(resolve_ours(merged), ("a\nmiddle\nb\n", 2))

    def test_rejects_unterminated_hunk(self):
        with self.assertRaises(ConflictFormatError):
            resolve_ours("<<<<<<< HEAD\nfork\n=======\nupstream\n")

    def test_rejects_text_without_conflicts(self):
        with self.assertRaises(ConflictFormatError):
            resolve_ours("ordinary file\n")

    def test_rejects_conflict_without_fork_marker(self):
        conflict = "<<<<<<< HEAD\nunrelated\n=======\nupstream\n>>>>>>> tag\n"
        with self.assertRaises(ConflictFormatError):
            resolve_ours(conflict, ("required fork marker",))

    def test_accepts_conflict_with_fork_marker(self):
        conflict = "<<<<<<< HEAD\nfork marker\n=======\nupstream\n>>>>>>> tag\n"
        self.assertEqual(resolve_ours(conflict, ("fork marker",)), ("fork marker\n", 1))

    def test_accepts_whitespace_only_conflict(self):
        conflict = "<<<<<<< HEAD\n=======\n\n>>>>>>> tag\n"
        self.assertEqual(resolve_ours(conflict, ("fork marker",)), ("", 1))

    def test_cli_rejects_non_allowlisted_path(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(["unknown/file.kt"])

    def test_cli_does_not_partially_write_on_later_failure(self):
        valid = "<<<<<<< HEAD\nfork\n=======\nupstream\n>>>>>>> tag\n"
        malformed = "<<<<<<< HEAD\nfork\n=======\nupstream\n"
        with TemporaryDirectory() as directory:
            original_cwd = Path.cwd()
            try:
                os.chdir(directory)
                Path("first.kt").write_text(valid, encoding="utf-8")
                Path("second.kt").write_text(malformed, encoding="utf-8")
                markers = {"first.kt": ("fork",), "second.kt": ("fork",)}
                with (
                    patch("resolve_upstream_conflicts.PATCH_MARKERS", markers),
                    patch("resolve_upstream_conflicts.ALLOWED_PATHS", frozenset(markers)),
                    redirect_stderr(StringIO()),
                ):
                    self.assertEqual(main(["first.kt", "second.kt"]), 1)
                self.assertEqual(Path("first.kt").read_text(encoding="utf-8"), valid)
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
