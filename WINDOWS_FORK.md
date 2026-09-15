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
`tasks/tasks` release tags once per day. A lightweight Ubuntu job exits without
starting a Windows runner when there is no new release.

For a new numeric release tag, the workflow merges that official tag, restores
the shared fork-managed files from that exact upstream tag, and reapplies the
small reviewed delta in `scripts/windows-fork.patch`. It then verifies the
premium unlock, OAuth, updater, and icon patches and runs the desktop tests. It
pushes the result to an isolated `automation/upstream-<version>` candidate
branch, not to `main`.

The Windows runner checks out that exact candidate SHA, repeats patch
verification and desktop tests, and builds the MSI. Only after the validated MSI
has been uploaded as a workflow artifact does the publish job promote the
candidate to `main` with a compare-and-swap push. If `main` changed during the
build, promotion is rejected instead of overwriting newer work. The GitHub
Release is then published and the temporary candidate branch is removed.

`scripts/resolve_upstream_conflicts.py` owns an explicit list of shared files.
For every release it replaces those files with the new upstream versions first,
then applies `scripts/windows-fork.patch` with Git's three-way patch support.
This makes upstream the source of truth instead of retaining an old fork side of
a conflict hunk. Unknown conflicts, a patch that no longer applies cleanly,
missing patch markers, or failing tests stop before `main` is pushed and open an
issue for manual review.

If the version marker was advanced but the GitHub Release or MSI is missing,
the scheduled workflow retries the Windows build instead of treating the
release as complete. A successful release closes earlier upstream-update
issues automatically.

When a fork patch starts modifying another upstream-owned file, add that file
to the workflow allowlist only after adding a fail-safe marker check or test for
the behavior. Fork-only implementation should remain in separate files when
possible.

Upstream workflow files are never imported, so automatic updates remain
Windows-only.
