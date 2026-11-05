# Windows fork maintenance

This branch tracks the official numeric `tasks/tasks` release tags. The
Windows-only customizations are kept as small, guarded patches so the scheduled
workflow can carry them across future releases.

The independently distributed desktop build unlocks premium features with one
guarded `IS_GENERIC` flag in `DesktopModule.kt`. This does not create or
impersonate a Tasks.org Cloud subscription.

The Windows build checks the fork's latest GitHub Release after the main window
has opened, downloads the matching MSI and checksum in the background, and only
offers installation after SHA-256 verification. The fixed MSI `upgradeUuid`
allows that installer to replace the existing installation. Update checks are
limited to once per day and do not delay the visible application startup.

The packaged runtime uses the upstream-maintained explicit JDK module list
instead of bundling every JDK module. Both the MSI and the running window use
the Tasks.org icon from `graphics/icon.ico` and the Compose resources.

## Manual development update

Start from a clean working tree and run:

```powershell
.\scripts\update-upstream.ps1
```

To also create a Windows installer after updating:

```powershell
.\scripts\update-upstream.ps1 -BuildInstaller
```

If an upstream change conflicts with the Windows patch, Git stops without
discarding work. Resolve the conflict and run `git rebase --continue`, or return
to the previous version with `git rebase --abort`.

This manual command rebases onto the latest upstream `main` for development and
may include unreleased changes. Official Windows releases use the numeric-tag
automation below.

The MSI is generated under `composeApp\build\compose\binaries\main\msi`.

## Automatic official releases

`.github/workflows/upstream-auto-release.yml` checks the official
`tasks/tasks` release tags once per day. A lightweight Ubuntu job exits before
starting platform build runners when no desktop package needs to be built.

For a new numeric release tag, the workflow merges that official tag and uses
upstream's version whenever both sides changed the same lines. It restores the
fork's release workflows and `README.md`, then rebuilds the desktop-specific
changes from the small reviewed delta in `scripts/windows-fork.patch` and
fork-only files. `.gitignore` rules are unioned. It then verifies the premium
unlock, OAuth, updater, and icon patches and runs the desktop tests. The
candidate is pushed to an isolated `automation/upstream-<version>` branch, not
to `main`. `.gitattributes` keeps the patch file's line endings as LF so Windows
checkouts can replay it reliably.

Each build runner checks out that exact candidate SHA. The Ubuntu prepare job
runs the desktop test suite once; Windows verifies the fork patches and builds
the MSI. A shared SQLite-native build and desktop-JAR build are reused across
the platform packages. Conveyor builds Windows MSIX and ZIP packages for x64
and ARM64 (the ZIPs include the upstream Windows executables), Linux DEB and
tar.gz packages for x86_64 and ARM64, and unnotarized macOS ZIP packages for
Intel and Apple Silicon. Windows App Installer manifests
point to the fork's latest GitHub Release so MSIX installations can update
automatically. The Linux tarballs are also used to build x86_64 and aarch64
AppImages with zsync update metadata. These follow the upstream desktop release
targets.

The publish job verifies every required package and SHA-256 checksum before
promoting the candidate to `main` with a compare-and-swap push. If `main` changed
during the builds, promotion is rejected instead of overwriting newer work.
Only after all artifacts pass validation does the GitHub Release receive the
Windows MSI/MSIX/ZIP packages, App Installer manifests, Linux DEB/tar.gz/AppImage
packages, macOS ZIP packages, and their checksums; then the temporary candidate
branch is removed. macOS packages are not notarized.

Build workflows read the required JDK version from
`gradle/libs.versions.toml`, so CI, manual builds, and releases follow the
project's declared toolchain instead of a fork-maintained fixed version. The
automatic updater resolves the latest upstream tag first and selects that
tag's JDK before running candidate tests (JDK 25 for Tasks.org 15.13).

`scripts/resolve_upstream_conflicts.py` owns an explicit list of shared files.
For every release it replaces those files with the new upstream versions first,
then applies `scripts/windows-fork.patch` with Git's three-way patch support.
This makes upstream the source of truth instead of retaining an old fork side of
a conflict hunk. Structural conflicts that Git cannot resolve, a patch that no
longer applies cleanly, missing patch markers, or failing tests stop before
`main` is pushed and open an issue for manual review.

If the version marker was advanced but any required platform package is missing
from the GitHub Release, the scheduled workflow retries the missing release
instead of treating it as complete. A successful release closes earlier
upstream-update issues automatically.

When a fork patch starts modifying another upstream-owned file, add that file
to the workflow allowlist only after adding a fail-safe marker check or test for
the behavior. Fork-only implementation should remain in separate files when
possible.

Upstream workflow files are never imported; the fork's workflow builds and
publishes Windows, Linux, and macOS desktop packages.
