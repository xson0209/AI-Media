$ErrorActionPreference = 'Continue'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path.TrimEnd('\')
$cache = (Resolve-Path (Join-Path $workspace '.cache')).Path.TrimEnd('\')
$blocked = (Resolve-Path (Join-Path $cache 'temp\pytest-of-xson0\pytest-5')).Path.TrimEnd('\')
if ($cache -eq $workspace -or -not $cache.StartsWith($workspace + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Unsafe cache target: $cache"
}
if (-not $blocked.StartsWith($cache + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Unsafe blocked target: $blocked"
}
Write-Output "CACHE=$cache"
Write-Output "BLOCKED=$blocked"
takeown.exe /F $blocked /R /D Y
icacls.exe $blocked /grant "${env:USERNAME}:(OI)(CI)F" /T /C
attrib.exe -R -S -H "$blocked\*" /S /D
Get-ChildItem -Force -LiteralPath $cache -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.FullName -eq (Split-Path -Parent (Split-Path -Parent $blocked))) { return }
  Remove-Item -Force -Recurse -LiteralPath $_.FullName -ErrorAction Continue
}
$pytestRoot = Split-Path -Parent $blocked
Get-ChildItem -Force -LiteralPath $pytestRoot -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.FullName -ne $blocked) {
    Remove-Item -Force -Recurse -LiteralPath $_.FullName -ErrorAction Continue
  }
}
try {
  [System.IO.Directory]::Delete($blocked, $true)
} catch {
  Write-Output "DIRECTORY_API_FAILED=$($_.Exception.Message)"
}
Remove-Item -Force -Recurse -LiteralPath $cache -ErrorAction Continue
if (Test-Path -LiteralPath $cache) {
  Write-Output 'CACHE_REMAINS'
  Get-ChildItem -Force -Recurse -LiteralPath $cache -ErrorAction SilentlyContinue |
    Select-Object -First 100 FullName,Mode,Length
} else {
  Write-Output 'CACHE_REMOVED'
}
