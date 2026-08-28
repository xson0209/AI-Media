$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CacheRoot = Join-Path $ProjectRoot ".cache"
$DataRoot = Join-Path $ProjectRoot "data"
$ModelsRoot = Join-Path $DataRoot "models"

$Directories = @(
    (Join-Path $CacheRoot "temp"),
    (Join-Path $CacheRoot "pip"),
    (Join-Path $CacheRoot "bun"),
    (Join-Path $CacheRoot "torch"),
    (Join-Path $CacheRoot "numba"),
    $ModelsRoot,
    (Join-Path $ModelsRoot ".hf"),
    (Join-Path $ModelsRoot ".xet"),
    (Join-Path $DataRoot "cache"),
    (Join-Path $ProjectRoot ".logs")
)

foreach ($Directory in $Directories) {
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
}

$env:TMP = Join-Path $CacheRoot "temp"
$env:TEMP = Join-Path $CacheRoot "temp"
$env:TMPDIR = Join-Path $CacheRoot "temp"

$env:PIP_CACHE_DIR = Join-Path $CacheRoot "pip"
$env:BUN_INSTALL_CACHE_DIR = Join-Path $CacheRoot "bun"
$env:UV_CACHE_DIR = Join-Path $CacheRoot "uv"

$env:HF_HOME = Join-Path $ModelsRoot ".hf"
$env:HF_HUB_CACHE = $ModelsRoot
$env:HF_XET_CACHE = Join-Path $ModelsRoot ".xet"
$env:TRANSFORMERS_CACHE = $ModelsRoot
$env:TORCH_HOME = Join-Path $CacheRoot "torch"
$env:XDG_CACHE_HOME = $CacheRoot
$env:NUMBA_CACHE_DIR = Join-Path $CacheRoot "numba"
$env:CUDA_MODULE_LOADING = "LAZY"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

$env:VOICEBOX_DATA_DIR = $DataRoot
$env:VOICEBOX_MODELS_DIR = $ModelsRoot
$env:VOICEBOX_CACHE_DIR = Join-Path $DataRoot "cache"
$env:VOICEBOX_BACKEND_HOST = "127.0.0.1"
$env:VOICEBOX_BACKEND_PORT = "17493"
$env:VOICEBOX_FRONTEND_PORT = "4000"
$env:VITE_SERVER_URL = "http://127.0.0.1:17493"
$env:VOICEBOX_FEATURE_AUTOMATION_HUB = "true"
$env:VOICEBOX_FEATURE_AUTOMATION_HUB_TIKTOK_DIRECT_POST = "false"

$SoxDir = Join-Path $ProjectRoot "tools\sox-14.4.2"
$SystemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$CurrentPath = $env:Path
$PathParts = @($SoxDir, $SystemPath, $UserPath, $CurrentPath) | Where-Object { $_ }
$env:Path = ($PathParts -join ";")

$CodexCommand = Get-Command codex.cmd -ErrorAction SilentlyContinue
if (-not $CodexCommand) {
    $CodexCommand = Get-Command codex -ErrorAction SilentlyContinue
}
if ($CodexCommand) {
    $env:VOICEBOX_CODEX_PATH = $CodexCommand.Source
}

Write-Host "Project root: $ProjectRoot"
Write-Host "Cache root:   $CacheRoot"
Write-Host "Data root:    $DataRoot"
Write-Host "Models root:  $ModelsRoot"
