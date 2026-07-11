$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env-local-e.ps1")

$Python = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"
$TorchIndexUrl = "https://download.pytorch.org/whl/cu126"
$TorchVersion = "2.11.0+cu126"
$TorchAudioVersion = "2.11.0+cu126"

if (-not (Test-Path -LiteralPath $Python)) {
    python -m venv (Join-Path $ProjectRoot "backend\venv")
}

& $Python -m pip install --upgrade pip
Write-Host "Installing CUDA PyTorch $TorchVersion for NVIDIA GPU..."
& $Python -m pip install --upgrade "torch==$TorchVersion" "torchaudio==$TorchAudioVersion" --index-url $TorchIndexUrl --extra-index-url "https://pypi.org/simple"
& $Python -m pip install -r (Join-Path $ProjectRoot "backend\requirements-qwen17.txt")
& $Python -m pip install --no-deps qwen-tts

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "tools\sox-14.4.2\sox.exe"))) {
    $ToolsDir = Join-Path $ProjectRoot "tools"
    $ZipPath = Join-Path $ToolsDir "sox-14.4.2-win32.zip"
    New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
    curl.exe -L "https://downloads.sourceforge.net/project/sox/sox/14.4.2/sox-14.4.2-win32.zip" -o $ZipPath
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $ToolsDir -Force
}

Push-Location $ProjectRoot
try {
    bun install --cache-dir (Join-Path $ProjectRoot ".cache\bun")
} finally {
    Pop-Location
}

Write-Host "Qwen 1.7B local setup complete."
