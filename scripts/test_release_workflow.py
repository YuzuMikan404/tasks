import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


class ReleaseWorkflowSafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (REPO / ".github/workflows/upstream-auto-release.yml").read_text(
            encoding="utf-8"
        )
        cls.manual_workflow = (REPO / ".github/workflows/windows-release.yml").read_text(
            encoding="utf-8"
        )
        cls.prepare = (REPO / "scripts/prepare_upstream_release.sh").read_text(
            encoding="utf-8"
        )
        cls.promote = (REPO / "scripts/promote_windows_release.sh").read_text(
            encoding="utf-8"
        )
        cls.jdk_action = (REPO / ".github/actions/setup-project-jdk/action.yml").read_text(
            encoding="utf-8"
        )
        cls.resolve_upstream = (REPO / "scripts/resolve_upstream_release.sh").read_text(
            encoding="utf-8"
        )
        cls.read_jdk_version = REPO / "scripts/read_jdk_version.sh"

    @staticmethod
    def bash_executable():
        bash = shutil.which("bash")
        if bash:
            return bash

        git_exec_path = subprocess.run(
            ("git", "--exec-path"),
            check=True,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        for parent in Path(git_exec_path).parents:
            for relative in ("bin/bash.exe", "usr/bin/bash.exe"):
                candidate = parent / relative
                if candidate.is_file():
                    return str(candidate)
        raise unittest.SkipTest("Bash is required for release script integration tests.")

    @classmethod
    def run_jdk_parser(cls, catalog):
        return subprocess.run(
            (cls.bash_executable(), str(cls.read_jdk_version)),
            input=catalog,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def test_publish_requires_the_complete_build_matrix(self):
        for job in ("windows", "windows_bundle", "linux", "macos", "appimage"):
            self.assertIn(f"needs.{job}.result == 'success'", self.workflow)
        self.assertIn("      - windows_bundle", self.workflow)
        self.assertIn("Atomically promote and publish candidate", self.workflow)
        self.assertIn("verify_desktop_release_artifacts.sh release-files", self.promote)

    def test_linux_and_macos_match_the_upstream_release_matrix(self):
        expected_targets = (
            "debian-package",
            "linux-tarball",
            "unnotarized-mac-zip",
            "windows-msix",
            "windows-zip",
            "windows.amd64",
            "windows.aarch64",
            "linux.amd64.glibc",
            "linux.aarch64.glibc",
            "mac.amd64",
            "mac.aarch64",
            "*_amd64.deb",
            "*_arm64.deb",
            "*-linux-amd64.tar.gz",
            "*-linux-aarch64.tar.gz",
            "*-mac-amd64.zip",
            "*-mac-aarch64.zip",
            "*.x64.msix",
            "*.arm64.msix",
            "*-windows-amd64.zip",
            "*-windows-aarch64.zip",
            "*.appinstaller",
        )
        for workflow in (self.workflow, self.manual_workflow):
            for target in expected_targets:
                self.assertIn(target, workflow)
            self.assertIn("shared-desktop-jar", workflow)
            self.assertIn("CONVEYOR_AGREE_TO_LICENSE", workflow)
            self.assertIn("desktop-linux-appimage", workflow)

    def test_release_completion_checks_every_supported_asset(self):
        required_suffixes = (
            "_amd64.deb",
            "_arm64.deb",
            "-linux-amd64.tar.gz",
            "-linux-aarch64.tar.gz",
            "-mac-amd64.zip",
            "-mac-aarch64.zip",
            "tasks-org-linux-x86_64.AppImage",
            "tasks-org-linux-aarch64.AppImage",
            "tasks-org-linux-x86_64.AppImage.zsync",
            "tasks-org-linux-aarch64.AppImage.zsync",
        )
        for suffix in required_suffixes:
            self.assertIn(suffix, self.prepare)
        for suffix in (
            "-windows-amd64.zip",
            "-windows-aarch64.zip",
            ".x64.msix",
            ".arm64.msix",
            "*.appinstaller",
        ):
            self.assertIn(suffix, self.prepare)
        verifier = (REPO / "scripts/verify_desktop_release_artifacts.sh").read_text(
            encoding="utf-8"
        )
        for suffix in required_suffixes:
            self.assertIn(suffix, verifier)
        self.assertIn('"$asset.sha256"', verifier)
        for pattern in (
            "tasks-org-*.x64.msix",
            "tasks-org-*.arm64.msix",
            "*-windows-amd64.zip",
            "*-windows-aarch64.zip",
            "*.appinstaller:2",
        ):
            self.assertIn(pattern, verifier)

    def test_manual_publish_downloads_and_verifies_all_artifacts(self):
        for pattern in (
            "tasks-org-windows-${{ github.sha }}",
            "desktop-windows-*",
            "desktop-linux-*",
            "desktop-macos-*",
        ):
            self.assertIn(pattern, self.manual_workflow)
        self.assertIn("bash scripts/verify_desktop_release_artifacts.sh release-files", self.manual_workflow)
        self.assertIn("needs:\n      - windows\n      - windows_bundle\n      - linux\n      - macos\n      - appimage", self.manual_workflow)

    def test_artifact_verifier_accepts_complete_release_and_rejects_bad_checksum(self):
        names = (
            "tasks-org-windows-x64-15.13.0.msi",
            "tasks-org-15.13.0.x64.msix",
            "tasks-org-15.13.0.arm64.msix",
            "tasks-org-15.13.0-windows-amd64.zip",
            "tasks-org-15.13.0-windows-aarch64.zip",
            "tasks-org-ha4v529wr7h46.appinstaller",
            "tasks-org-ha4v529wr7h46-arm64.appinstaller",
            "tasks-org_15.13.0_amd64.deb",
            "tasks-org_15.13.0_arm64.deb",
            "tasks-org-15.13.0-linux-amd64.tar.gz",
            "tasks-org-15.13.0-linux-aarch64.tar.gz",
            "tasks-org-15.13.0-mac-amd64.zip",
            "tasks-org-15.13.0-mac-aarch64.zip",
            "tasks-org-linux-x86_64.AppImage",
            "tasks-org-linux-x86_64.AppImage.zsync",
            "tasks-org-linux-aarch64.AppImage",
            "tasks-org-linux-aarch64.AppImage.zsync",
        )
        verifier = REPO / "scripts/verify_desktop_release_artifacts.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            for name in names:
                asset = release_dir / name
                asset.write_bytes(name.encode("ascii"))
                checksum = f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {name}\n"
                (release_dir / f"{name}.sha256").write_bytes(checksum.encode("ascii"))

            valid = subprocess.run(
                (self.bash_executable(), str(verifier), str(release_dir)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)

            arm_manifest = release_dir / names[6]
            unrelated_arm_manifest = release_dir / "unrelated-arm64.appinstaller"
            arm_manifest.rename(unrelated_arm_manifest)
            (release_dir / f"{names[6]}.sha256").unlink()
            bad_manifest_checksum = (
                f"{hashlib.sha256(unrelated_arm_manifest.read_bytes()).hexdigest()}  "
                f"{unrelated_arm_manifest.name}\n"
            )
            (release_dir / f"{unrelated_arm_manifest.name}.sha256").write_bytes(
                bad_manifest_checksum.encode("ascii")
            )
            mismatched = subprocess.run(
                (self.bash_executable(), str(verifier), str(release_dir)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(mismatched.returncode, 0)

            unrelated_arm_manifest.rename(arm_manifest)
            (release_dir / f"{unrelated_arm_manifest.name}.sha256").unlink()
            restored_manifest_checksum = (
                f"{hashlib.sha256(arm_manifest.read_bytes()).hexdigest()}  "
                f"{arm_manifest.name}\n"
            )
            (release_dir / f"{arm_manifest.name}.sha256").write_bytes(
                restored_manifest_checksum.encode("ascii")
            )
            (release_dir / names[0]).write_bytes(b"tampered")
            invalid = subprocess.run(
                (self.bash_executable(), str(verifier), str(release_dir)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(invalid.returncode, 0)

    def test_prepare_never_pushes_main(self):
        self.assertNotIn("refs/heads/main", self.prepare)
        self.assertIn('candidate_branch="automation/upstream-$latest"', self.prepare)

    def test_upstream_wins_conflicts_and_fork_readme_is_preserved(self):
        self.assertIn(
            'git merge --no-ff --no-edit -X theirs "refs/tags/upstream-$latest"',
            self.prepare,
        )
        self.assertIn(
            'git checkout "$fork_head" -- .gitattributes .github/actions/setup-project-jdk .github/workflows README.md WINDOWS_FORK.md',
            self.prepare,
        )
        self.assertIn("      .gitattributes) ;;", self.prepare)

    def test_desktop_tests_run_on_linux_not_windows(self):
        self.assertIn("./gradlew :composeApp:desktopTest --console=plain", self.prepare)
        self.assertNotIn(
            ":composeApp:desktopTest",
            self.workflow[self.workflow.index("  windows:"):],
        )
        self.assertIn(
            "run: ./gradlew :composeApp:desktopTest --console=plain",
            self.manual_workflow,
        )
        self.assertNotIn(":composeApp:desktopTest", self.manual_workflow[
            self.manual_workflow.index("  windows:"):self.manual_workflow.index("  desktop_jar:")
        ])

    def test_release_jobs_build_and_share_sqlite_natives(self):
        for workflow in (self.workflow, self.manual_workflow):
            self.assertIn("  sqlite_natives:", workflow)
            self.assertIn("composeApp/build-sqlite-natives.sh", workflow)
            self.assertIn("actions/upload-artifact@v7", workflow)
            self.assertIn("actions/download-artifact@v8", workflow)
            self.assertIn(":composeApp:packageMsi", workflow)
            jar_line = next(
                line for line in workflow.splitlines() if ":composeApp:desktopJar" in line
            )
            self.assertIn("-PsqliteNatives=", jar_line)

    def test_release_scripts_and_patches_keep_lf_line_endings(self):
        result = subprocess.run(
            (
                "git",
                "check-attr",
                "eol",
                "--",
                "scripts/windows-fork.patch",
                "scripts/fetch",
                "scripts/resolve_upstream_release.sh",
                "scripts/read_jdk_version.sh",
                "scripts/verify_desktop_release_artifacts.sh",
            ),
            cwd=REPO,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.assertIn("scripts/windows-fork.patch: eol: lf", result.stdout)
        self.assertIn("scripts/fetch: eol: lf", result.stdout)
        self.assertIn("scripts/resolve_upstream_release.sh: eol: lf", result.stdout)
        self.assertIn("scripts/read_jdk_version.sh: eol: lf", result.stdout)
        self.assertIn("scripts/verify_desktop_release_artifacts.sh: eol: lf", result.stdout)

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

    def test_build_workflows_use_upstream_jdk_version(self):
        workflows = (
            self.workflow,
            self.manual_workflow,
            (REPO / ".github/workflows/check.yml").read_text(encoding="utf-8"),
            (REPO / ".github/workflows/dependency_diff.yml").read_text(encoding="utf-8"),
        )
        for workflow in workflows:
            self.assertNotIn("java-version: \"25\"", workflow)
            self.assertNotIn("java-version: '25'", workflow)
            self.assertIn("./.github/actions/setup-project-jdk", workflow)
        self.assertIn("gradle/libs.versions.toml", self.jdk_action)
        self.assertIn("java-version: ${{ steps.resolve.outputs.version }}", self.jdk_action)
        self.assertIn("steps.upstream.outputs.jdk_version", self.workflow)
        self.assertIn("gradle/libs.versions.toml", self.resolve_upstream)
        self.assertIn("refs/tags/upstream-$latest", self.resolve_upstream)
        self.assertIn('bash "$script_dir/read_jdk_version.sh"', self.resolve_upstream)
        self.assertIn("UPSTREAM_TAG_REF_SHA", self.prepare)
        self.assertIn('git merge-base --is-ancestor "$actual_tag_sha" "$base_sha"', self.prepare)
        self.assertIn("Refusing to downgrade upstream", self.prepare)
        self.assertLess(
            self.prepare.index('echo "base_sha=$base_sha"'),
            self.prepare.index('if [ "$same_upstream_tag" = true ]'),
        )

    def test_jdk_parser_accepts_catalog_values_and_rejects_ambiguous_values(self):
        for catalog, expected in (
            ('jdk = "25"\n', "25"),
            ('  jdk = 21 # catalog comment\r\n', "21"),
        ):
            with self.subTest(catalog=catalog):
                result = self.run_jdk_parser(catalog)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

        for catalog in (
            "",
            'jdk = "25"\njdk = "26"\n',
            'jdk = "0"\n',
            'jdk = "25.0"\n',
            "jdk = { version = 25 }\n",
            'jdk = "25"\njdk = "invalid"\n',
        ):
            with self.subTest(catalog=catalog):
                result = self.run_jdk_parser(catalog)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_upstream_resolver_selects_latest_numeric_tag_and_checks_tag_object(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            remote = root / "upstream.git"
            seed = root / "seed"
            work = root / "work"
            output = root / "github-output"
            output.touch()

            subprocess.run(("git", "init", "--bare", str(remote)), check=True, capture_output=True)
            subprocess.run(("git", "init", str(seed)), check=True, capture_output=True)
            subprocess.run(("git", "config", "user.name", "test"), cwd=seed, check=True)
            subprocess.run(("git", "config", "user.email", "test@example.com"), cwd=seed, check=True)
            (seed / "gradle").mkdir()
            catalog = seed / "gradle/libs.versions.toml"
            catalog.write_text('jdk = "21"\n', encoding="utf-8")
            subprocess.run(("git", "add", "."), cwd=seed, check=True)
            subprocess.run(("git", "commit", "-m", "release 15.12"), cwd=seed, check=True, capture_output=True)
            subprocess.run(("git", "tag", "15.12"), cwd=seed, check=True)

            catalog.write_text('jdk = "25" # latest toolchain\n', encoding="utf-8")
            subprocess.run(("git", "add", "."), cwd=seed, check=True)
            subprocess.run(("git", "commit", "-m", "release 15.13"), cwd=seed, check=True, capture_output=True)
            subprocess.run(("git", "tag", "-a", "15.13", "-m", "annotated release"), cwd=seed, check=True)
            subprocess.run(("git", "tag", "v99.0"), cwd=seed, check=True)
            subprocess.run(("git", "push", str(remote), "refs/tags/15.12", "refs/tags/15.13", "refs/tags/v99.0"), cwd=seed, check=True, capture_output=True)

            subprocess.run(("git", "init", str(work)), check=True, capture_output=True)
            subprocess.run(("git", "config", "user.name", "test"), cwd=work, check=True)
            subprocess.run(("git", "config", "user.email", "test@example.com"), cwd=work, check=True)
            (work / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(("git", "add", "."), cwd=work, check=True)
            subprocess.run(("git", "commit", "-m", "base"), cwd=work, check=True, capture_output=True)
            subprocess.run(("git", "remote", "add", "upstream", str(remote)), cwd=work, check=True)

            env = os.environ.copy()
            env["GITHUB_OUTPUT"] = str(output)
            env["UPSTREAM_REMOTE_URL"] = str(remote)
            result = subprocess.run(
                (self.bash_executable(), str(REPO / "scripts/resolve_upstream_release.sh")),
                cwd=work,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
            self.assertEqual(outputs["version"], "15.13")
            self.assertEqual(outputs["jdk_version"], "25")
            self.assertEqual(
                outputs["tag_ref_sha"],
                subprocess.run(
                    ("git", "rev-parse", "refs/tags/upstream-15.13"),
                    cwd=work,
                    check=True,
                    stdout=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                ).stdout.strip(),
            )
            self.assertEqual(
                outputs["tag_sha"],
                subprocess.run(
                    ("git", "rev-parse", "refs/tags/upstream-15.13^{commit}"),
                    cwd=work,
                    check=True,
                    stdout=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                ).stdout.strip(),
            )

            catalog.write_text('jdk = "not-a-version"\n', encoding="utf-8")
            subprocess.run(("git", "add", "."), cwd=seed, check=True)
            subprocess.run(("git", "commit", "-m", "invalid release toolchain"), cwd=seed, check=True, capture_output=True)
            subprocess.run(("git", "tag", "15.14"), cwd=seed, check=True)
            subprocess.run(("git", "push", str(remote), "refs/tags/15.14"), cwd=seed, check=True, capture_output=True)

            failed_output = root / "failed-output"
            failed_output.touch()
            env["GITHUB_OUTPUT"] = str(failed_output)
            result = subprocess.run(
                (self.bash_executable(), str(REPO / "scripts/resolve_upstream_release.sh")),
                cwd=work,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(failed_output.read_text(), "")

            subprocess.run(
                (
                    "git",
                    "push",
                    str(remote),
                    ":refs/tags/15.12",
                    ":refs/tags/15.13",
                    ":refs/tags/15.14",
                ),
                cwd=seed,
                check=True,
                capture_output=True,
            )
            no_release_output = root / "no-release-output"
            no_release_output.touch()
            env["GITHUB_OUTPUT"] = str(no_release_output)
            result = subprocess.run(
                (self.bash_executable(), str(REPO / "scripts/resolve_upstream_release.sh")),
                cwd=work,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No official numeric release tag", result.stdout + result.stderr)
            self.assertEqual(no_release_output.read_text(), "")


if __name__ == "__main__":
    unittest.main()
