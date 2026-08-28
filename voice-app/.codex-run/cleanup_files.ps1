$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path.TrimEnd('\')
$targets = @(
  'data\ai-video\provider-downloads',
  'data\backups',
  'data\cache',
  'data\captures',
  'data\comic_series_analysis',
  'data\db-backups',
  'data\generations',
  'data\logs',
  'data\research_projects',
  'data\video_inspiration',
  'data\video_projects',
  'data\video_series',
  'output',
  '.logs',
  '.codex-temp',
  '.pytest_cache',
  '.ruff_cache',
  '.playwright-cli',
  'app\.playwright-cli'
)
$browserCacheTargets = Get-ChildItem -Force -Recurse -Directory -LiteralPath (Join-Path $workspace 'data\ai-video\browser-profiles') -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @('Cache','Code Cache','GPUCache','DawnCache','GrShaderCache','GraphiteDawnCache','ShaderCache','CacheStorage','Media Cache') } |
  Sort-Object { $_.FullName.Length } -Descending |
  Select-Object -ExpandProperty FullName
$resolvedTargets = @()
foreach ($target in @($targets + $browserCacheTargets)) {
  $candidate = Join-Path $workspace $target
  if (-not (Test-Path -LiteralPath $candidate)) { continue }
  $resolved = (Resolve-Path -LiteralPath $candidate).Path.TrimEnd('\')
  if ($resolved -eq $workspace -or -not $resolved.StartsWith($workspace + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe deletion target: $resolved"
  }
  $resolvedTargets += $resolved
}
$rootGeneratedLogs = Get-ChildItem -Force -File -LiteralPath $workspace | Where-Object { $_.Extension -eq '.log' }
$backupDbFiles = Get-ChildItem -Force -File -LiteralPath (Join-Path $workspace 'data') | Where-Object { $_.Name -like 'voicebox-before-*.db' }
$fileTargets = @($rootGeneratedLogs + $backupDbFiles)
$bytes = 0L
$files = 0L
foreach ($resolved in $resolvedTargets) {
  $item = Get-Item -Force -LiteralPath $resolved
  if ($item.PSIsContainer) {
    $stats = Get-ChildItem -Force -Recurse -File -LiteralPath $resolved -ErrorAction SilentlyContinue | Measure-Object Length -Sum
    $bytes += [int64]$stats.Sum
    $files += [int64]$stats.Count
  } else {
    $bytes += [int64]$item.Length
    $files += 1
  }
}
foreach ($file in $fileTargets) { $bytes += [int64]$file.Length; $files += 1 }
Write-Output "DELETE_DIR_TARGETS=$($resolvedTargets.Count)"
Write-Output "DELETE_FILE_TARGETS=$($fileTargets.Count)"
Write-Output "DELETE_FILES=$files"
Write-Output "DELETE_BYTES=$bytes"
foreach ($resolved in $resolvedTargets) { Remove-Item -Force -Recurse -LiteralPath $resolved }
foreach ($file in $fileTargets) { Remove-Item -Force -LiteralPath $file.FullName }
Write-Output 'FILESYSTEM_CLEANUP_COMPLETE'
