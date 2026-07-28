param(
    [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    if (git status --porcelain) {
        throw "The working tree is not clean. Commit or stash local changes before updating."
    }

    $upstreamUrl = "https://github.com/tasks/tasks.git"
    $existingUpstream = git remote get-url upstream 2>$null
    if ($LASTEXITCODE -ne 0) {
        git remote add upstream $upstreamUrl
    } elseif ($existingUpstream -ne $upstreamUrl) {
        git remote set-url upstream $upstreamUrl
    }

    git fetch upstream main
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to fetch upstream/main."
    }

    git rebase upstream/main
    if ($LASTEXITCODE -ne 0) {
        throw "The upstream rebase needs manual conflict resolution. Run 'git rebase --abort' to return to the previous state."
    }

    & .\gradlew.bat :composeApp:compileKotlinDesktop --console=plain
    if ($LASTEXITCODE -ne 0) {
        throw "The updated desktop application did not compile."
    }

    if ($BuildInstaller) {
        & .\gradlew.bat :composeApp:packageMsi --console=plain
        if ($LASTEXITCODE -ne 0) {
            throw "The Windows MSI build failed."
        }
    }
} finally {
    Pop-Location
}
