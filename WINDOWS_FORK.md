# Windows fork maintenance

This branch is based directly on `tasks/tasks` `main`. The Windows-only
customizations are kept as small commits on top of upstream so they can be
rebased onto future releases.

The desktop build follows the F-Droid entitlement policy. Independently hosted
EteSync and CalDAV synchronization do not require a Tasks.org subscription.
This does not create a Tasks.org Cloud subscription.

## Update from upstream

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

The MSI is generated under `composeApp\build\compose\binaries\main\msi`.

## Automatic official releases

`.github/workflows/upstream-auto-release.yml` checks the official
`tasks/tasks` release tags once per day. A lightweight Ubuntu job exits without
starting a Windows runner when there is no new release.

For a new numeric release tag, the workflow merges that official tag, verifies
the libre entitlement and icon patches, tests and builds the Windows MSI, and
publishes a prerelease named `windows-v<official version>`. Merge conflicts or
missing patches stop the workflow before publishing.

Upstream workflow files are never imported, so automatic updates remain
Windows-only.
