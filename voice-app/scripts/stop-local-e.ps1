$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Add-ProcessId([System.Collections.Generic.HashSet[int]]$Set, $ProcessId) {
    if ($ProcessId -and $ProcessId -gt 0) {
        [void]$Set.Add([int]$ProcessId)
    }
}

$ProcessIds = [System.Collections.Generic.HashSet[int]]::new()

Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        ($_.CommandLine -match "backend\.main" -and $_.CommandLine -match [regex]::Escape($ProjectRoot)) -or
        ($_.CommandLine -match "vite" -and $_.CommandLine -match [regex]::Escape($ProjectRoot))
    )
} | ForEach-Object {
    Add-ProcessId $ProcessIds $_.ProcessId
}

Get-NetTCPConnection -LocalPort 17493,209 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Add-ProcessId $ProcessIds $_.OwningProcess
}

foreach ($ProcessId in $ProcessIds) {
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    if ($Process) {
        Write-Host "Stopped PID ${ProcessId}: $($Process.ProcessName)"
    } else {
        Write-Host "Stopped PID ${ProcessId}"
    }
}
