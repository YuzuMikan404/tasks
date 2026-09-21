from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parent.parent


class ReleaseWorkflowSafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (REPO / ".github/workflows/upstream-auto-release.yml").read_text(
            encoding="utf-8"
        )
        cls.prepare = (REPO / "scripts/prepare_upstream_release.sh").read_text(
            encoding="utf-8"
        )
        cls.promote = (REPO / "scripts/promote_windows_release.sh").read_text(
            encoding="utf-8"
        )

    def test_publish_requires_successful_windows_job(self):
        self.assertIn("needs.windows.result == 'success'", self.workflow)
        self.assertIn("needs.linux.result == 'success'", self.workflow)
        self.assertIn("Atomically promote and publish candidate", self.workflow)

    def test_linux_deb_is_built_and_published(self):
        self.assertIn(":composeApp:packageDeb", self.workflow)
        self.assertIn('if [ "$msi_count" -gt 0 ] && [ "$deb_count" -gt 0 ]', self.prepare)
        self.assertIn('deb="release-files/tasks-org-linux-x64-$VERSION.deb"', self.promote)
        self.assertIn('test -f "$deb"', self.promote)

    def test_prepare_never_pushes_main(self):
        self.assertNotIn("refs/heads/main", self.prepare)
        self.assertIn('candidate_branch="automation/upstream-$latest"', self.prepare)

    def test_main_promotion_is_fast_forward_and_race_checked(self):
        self.assertIn('current_main="$(git rev-parse origin/main)"', self.promote)
        self.assertIn('if [ "$current_main" != "$EXPECTED_BASE" ]', self.promote)
        self.assertIn('git push origin "$candidate:refs/heads/main"', self.promote)
        self.assertNotIn("--force-with-lease", self.promote)

    def test_superseded_candidate_is_a_successful_noop(self):
        stale_guard = self.promote.index('if [ "$current_main" != "$EXPECTED_BASE" ]')
        promotion = self.promote.index('git push origin "$candidate:refs/heads/main"')
        stale_path = self.promote[stale_guard:promotion]
        self.assertIn("candidate is superseded, skipping publication", stale_path)
        self.assertIn('remote_candidate="$(git ls-remote origin', stale_path)
        self.assertIn('if [ "$remote_candidate" = "$EXPECTED_CANDIDATE" ]', stale_path)
        self.assertIn("exit 0", stale_path)

    def test_release_happens_after_main_promotion(self):
        push = self.promote.index('git push origin "$candidate:refs/heads/main"')
        release = self.promote.index('gh release view "$tag"')
        cleanup = self.promote.rindex('git push origin --delete "$CANDIDATE_BRANCH"')
        self.assertLess(push, release)
        self.assertLess(release, cleanup)

    def test_artifact_download_enforces_current_digest_checks(self):
        self.assertIn("actions/download-artifact@v8", self.workflow)


if __name__ == "__main__":
    unittest.main()
