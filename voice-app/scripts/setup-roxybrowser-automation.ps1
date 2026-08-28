param(
    [string]$DataRoot = "",
    [string]$SourceRoot = "",
    [switch]$SkipInstall,
    [switch]$SkipUpdate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $DataRoot) {
    if ($env:VOICEBOX_DATA_DIR) {
        $DataRoot = $env:VOICEBOX_DATA_DIR
    } else {
        $DataRoot = Join-Path $repoRoot "data"
    }
}

$resolvedDataRoot = [System.IO.Path]::GetFullPath($DataRoot)
$targetRoot = Join-Path $resolvedDataRoot "automation_hub\roxybrowserlabs"
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null

if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    throw "Missing prerequisite 'git' in PATH."
}
if (-not $SkipInstall) {
    foreach ($commandName in @("node", "npm", "pnpm")) {
        if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
            throw "Missing prerequisite '$commandName' in PATH."
        }
    }
}

function Sync-RoxyRepository {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url
    )

    $target = Join-Path $targetRoot $Name
    if (-not (Test-Path -LiteralPath $target)) {
        $localSource = if ($SourceRoot) { Join-Path ([System.IO.Path]::GetFullPath($SourceRoot)) $Name } else { "" }
        if ($localSource -and (Test-Path -LiteralPath (Join-Path $localSource ".git"))) {
            & git clone --no-hardlinks $localSource $target | ForEach-Object { Write-Host $_ }
            if ($LASTEXITCODE -eq 0) {
                & git -C $target remote set-url origin $Url | ForEach-Object { Write-Host $_ }
            }
        } else {
            & git clone $Url $target | ForEach-Object { Write-Host $_ }
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Could not clone $Name."
        }
        return $target
    }

    $gitDir = Join-Path $target ".git"
    if (-not (Test-Path -LiteralPath $gitDir)) {
        throw "Target exists but is not a Git repository: $target"
    }

    $remote = (& git -C $target remote get-url origin).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $remote.Contains("roxybrowserlabs/$Name")) {
        throw "Remote origin does not match the expected RoxyBrowser repository: $target"
    }

    if (-not $SkipUpdate) {
        $dirty = & git -C $target status --porcelain
        if ($dirty) {
            Write-Warning "$Name has local changes; skipping git pull to preserve them."
        } else {
            & git -C $target pull --ff-only | ForEach-Object { Write-Host $_ }
            if ($LASTEXITCODE -ne 0) {
                throw "Could not update $Name with a fast-forward pull."
            }
        }
    }
    return $target
}

$localApi = Sync-RoxyRepository -Name "local-API" -Url "https://github.com/roxybrowserlabs/local-API.git"
$openApiMcp = Sync-RoxyRepository -Name "roxybrowser-mcp-server" -Url "https://github.com/roxybrowserlabs/roxybrowser-mcp-server.git"
$playwrightMcp = Sync-RoxyRepository -Name "roxybrowser-playwright-mcp" -Url "https://github.com/roxybrowserlabs/roxybrowser-playwright-mcp.git"

if (-not $SkipInstall) {
    Push-Location $openApiMcp
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed in roxybrowser-mcp-server." }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "Build failed in roxybrowser-mcp-server." }
    } finally {
        Pop-Location
    }

    Push-Location $playwrightMcp
    try {
        & pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw "pnpm install failed in roxybrowser-playwright-mcp." }
        & pnpm build
        if ($LASTEXITCODE -ne 0) { throw "Build failed in roxybrowser-playwright-mcp." }
    } finally {
        Pop-Location
    }
}

$entry = Join-Path $playwrightMcp "dist\bin\roxybrowser-mcp.js"
Write-Output "Prepared all three repositories at: $targetRoot"
Write-Output "local-API contains documentation/examples; the real Local API server runs in RoxyBrowser Desktop."
Write-Output "Playwright MCP entry: $entry"
Write-Output "Enable the backend with: `$env:VOICEBOX_FEATURE_AUTOMATION_HUB='true'"
Write-Output "For a custom data root, set: `$env:VOICEBOX_ROXY_PLAYWRIGHT_ENTRY='$entry'"
