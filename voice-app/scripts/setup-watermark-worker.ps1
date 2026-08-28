param(
    [ValidateSet("cv2", "migan")]
    [string]$Backend = "cv2",
    [string]$WatermarkRoot = ""
)

$ErrorActionPreference = "Stop"

$voiceboxRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $WatermarkRoot) {
    $WatermarkRoot = Join-Path (Split-Path -Parent $voiceboxRoot) "remove watermark"
}
$WatermarkRoot = [System.IO.Path]::GetFullPath($WatermarkRoot)

if (-not (Test-Path -LiteralPath (Join-Path $WatermarkRoot "pyproject.toml") -PathType Leaf)) {
    throw "remove-ai-watermarks repository not found at: $WatermarkRoot"
}

# Resolve uv: PATH first (respect a user-managed install), then the uv.exe that
# ships with the project's backend venv. The watermark worker venv is created by
# uv and has no pip, so uv is the only supported installer here.
$projectUvPath = Join-Path $voiceboxRoot "backend\venv\Scripts\uv.exe"
$uvPath = $null
$uvSource = $null

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvPath = $uvCommand.Source
    $uvSource = "PATH"
}
elseif (Test-Path -LiteralPath $projectUvPath -PathType Leaf) {
    $uvPath = $projectUvPath
    $uvSource = "project backend venv"
}

if (-not $uvPath) {
    throw @"
uv was not found. Looked in:
  1. PATH (command 'uv')
  2. project backend venv: $projectUvPath
Install uv, or restore the project's backend venv, then run this script again.
"@
}

Write-Host "Using uv from ${uvSource}: $uvPath"

$syncArgs = @("sync", "--project", $WatermarkRoot, "--extra", "video")
if ($Backend -eq "migan") {
    $syncArgs += @("--extra", "migan")
}

Write-Host "Preparing watermark worker ($Backend) at $WatermarkRoot"
& $uvPath @syncArgs
if ($LASTEXITCODE -ne 0) {
    throw "uv sync failed with exit code $LASTEXITCODE."
}

$pythonPath = Join-Path $WatermarkRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "uv sync completed but worker Python was not found at: $pythonPath"
}

Write-Host "Watermark worker is ready."
Write-Host "VOICEBOX_WATERMARK_ROOT=$WatermarkRoot"
Write-Host "VOICEBOX_WATERMARK_PYTHON=$pythonPath"
Write-Host "Restart the Voicebox backend after setting environment overrides."
