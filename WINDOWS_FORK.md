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
