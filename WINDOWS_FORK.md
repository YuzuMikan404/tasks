# Windows fork maintenance

This branch tracks the official numeric `tasks/tasks` release tags. The
Windows-only customizations are kept as small, guarded patches so the scheduled
workflow can carry them across future releases.

The desktop build follows the F-Droid entitlement policy. Independently hosted
EteSync and CalDAV synchronization do not require a Tasks.org subscription.
This does not create a Tasks.org Cloud subscription.

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

For a new numeric release tag, the workflow merges that official tag, reapplies
known Windows-fork conflict hunks, verifies the libre entitlement, OAuth, and
icon patches, and runs the desktop tests. It pushes the result to an isolated
`automation/upstream-<version>` candidate branch, not to `main`.

The Windows runner checks out that exact candidate SHA, repeats patch
verification and desktop tests, and builds the MSI. Only after the validated MSI
has been uploaded as a workflow artifact does the publish job promote the
candidate to `main` with a compare-and-swap push. If `main` changed during the
build, promotion is rejected instead of overwriting newer work. The GitHub
Release is then published and the temporary candidate branch is removed.

`scripts/resolve_upstream_conflicts.py` only handles an explicit allowlist of
files that contain small Windows-fork call-site patches. It keeps the fork side
only when that individual conflict hunk contains a registered fork marker,
while preserving all non-conflicting upstream changes Git already merged around
it. Unknown files, unrelated hunks in known files, malformed conflicts, missing
patch markers, or failing tests stop before `main` is pushed and open an issue
for manual review.

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
