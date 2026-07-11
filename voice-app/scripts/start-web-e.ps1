$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env-local-e.ps1")

$LogsDir = Join-Path $ProjectRoot ".logs"
$Python = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"
$BackendUrl = "http://127.0.0.1:$env:VOICEBOX_BACKEND_PORT"
$BackendReadyUrl = "$BackendUrl/health/ready"
$FrontendUrl = "http://127.0.0.1:$env:VOICEBOX_FRONTEND_PORT"
$BackendTimeoutSeconds = 180
$FrontendTimeoutSeconds = 90
$BackendProcess = $null
$FrontendProcess = $null

function Test-Url($Url) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-PortOwnerIds($Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -and $_ -gt 0 })
}

function Get-ProcessSummary($ProcessId) {
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $Process) {
        return "PID $ProcessId"
    }
    return "PID $ProcessId $($Process.Name) $($Process.CommandLine)"
}

function Stop-ProjectPortOwners($Port, $Name, [string[]]$Markers) {
    $OwnerIds = Get-PortOwnerIds $Port
    if (-not $OwnerIds.Count) {
        return
    }

    foreach ($OwnerId in $OwnerIds) {
        $Summary = Get-ProcessSummary $OwnerId
        $MatchesProject = $false
        foreach ($Marker in $Markers) {
            if ($Summary -match [regex]::Escape($Marker)) {
                $MatchesProject = $true
                break
            }
        }

        if (-not $MatchesProject) {
            throw "$Name port $Port is already used by another process: $Summary"
        }

        Write-Host "Stopping stale $Name listener on port ${Port}: $Summary"
        Stop-Process -Id $OwnerId -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 1
}

function Format-PortOwners($Port) {
    $OwnerIds = Get-PortOwnerIds $Port
    if (-not $OwnerIds.Count) {
        return "none"
    }
    return (($OwnerIds | ForEach-Object { Get-ProcessSummary $_ }) -join "; ")
}

function Reset-Log($Path) {
    $Parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    if (Test-Path -LiteralPath $Path) {
        Clear-Content -LiteralPath $Path
    } else {
        New-Item -ItemType File -Path $Path -Force | Out-Null
    }
}

function Show-LogTail($Label, $Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $Lines = Get-Content -LiteralPath $Path -Tail 40 -ErrorAction SilentlyContinue
    if (-not $Lines) {
        return
    }

    Write-Host ""
    Write-Host "$Label log tail:"
    foreach ($Line in $Lines) {
        Write-Host "  $Line"
    }
}

function Wait-ForUrl($Name, $Url, $TimeoutSeconds, $Process = $null, $Port = $null) {
    Write-Host "Waiting for ${Name}: $Url"
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $Deadline) {
        if (Test-Url $Url) {
            Write-Host "$Name ready: $Url"
            return
        }

        if ($Process) {
            $Process.Refresh()
            if ($Process.HasExited) {
                if ($Port -and (Get-PortOwnerIds $Port).Count) {
                    $Process = $null
                } else {
                    throw "$Name process exited before it became ready. Exit code: $($Process.ExitCode)"
                }
            }
        }

        Write-Host -NoNewline "."
        Start-Sleep -Seconds 2
    }

    Write-Host ""
    if ($Port) {
        throw "$Name did not become available after $TimeoutSeconds seconds: $Url. Port owners: $(Format-PortOwners $Port)"
    }
    throw "$Name did not become available after $TimeoutSeconds seconds: $Url"
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing backend venv. Run scripts\setup-qwen17-e.ps1 first."
}

$BackendOut = Join-Path $LogsDir "backend.out.log"
$BackendErr = Join-Path $LogsDir "backend.err.log"
$FrontendOut = Join-Path $LogsDir "web.out.log"
$FrontendErr = Join-Path $LogsDir "web.err.log"

if (Test-Url $BackendReadyUrl) {
    Write-Host "Backend already running: $BackendUrl"
} else {
    Stop-ProjectPortOwners $env:VOICEBOX_BACKEND_PORT "Backend" @(
        "backend.main",
        $ProjectRoot,
        "uvicorn"
    )
    Reset-Log $BackendOut
    Reset-Log $BackendErr
    $BackendProcess = Start-Process -FilePath $Python `
        -ArgumentList "-m", "backend.main" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $BackendOut `
        -RedirectStandardError $BackendErr `
        -PassThru
    Write-Host "Started backend PID $($BackendProcess.Id): $BackendUrl"
}

if (Test-Url $FrontendUrl) {
    Write-Host "Frontend already running: $FrontendUrl"
} else {
    Stop-ProjectPortOwners $env:VOICEBOX_FRONTEND_PORT "Frontend" @(
        $ProjectRoot,
        "vite",
        "bun"
    )
    $BunCommand = (Get-Command bun -ErrorAction Stop).Source
    Reset-Log $FrontendOut
    Reset-Log $FrontendErr

    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $ProjectRoot
        try {
            & $BunCommand install
            if ($LASTEXITCODE -ne 0) {
                throw "bun install failed with exit code $LASTEXITCODE"
            }
        } finally {
            Pop-Location
        }
    }

    $FrontendProcess = Start-Process -FilePath $BunCommand `
        -ArgumentList "run", "dev", "--host", "127.0.0.1", "--port", $env:VOICEBOX_FRONTEND_PORT `
        -WorkingDirectory (Join-Path $ProjectRoot "web") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendOut `
        -RedirectStandardError $FrontendErr `
        -PassThru
    Write-Host "Started frontend PID $($FrontendProcess.Id): $FrontendUrl"
}

try {
    Wait-ForUrl "Backend" $BackendReadyUrl $BackendTimeoutSeconds $BackendProcess $env:VOICEBOX_BACKEND_PORT
} catch {
    Show-LogTail "Backend stderr" $BackendErr
    Show-LogTail "Backend stdout" $BackendOut
    throw
}

try {
    Wait-ForUrl "Frontend" $FrontendUrl $FrontendTimeoutSeconds $FrontendProcess $env:VOICEBOX_FRONTEND_PORT
} catch {
    Show-LogTail "Frontend stderr" $FrontendErr
    Show-LogTail "Frontend stdout" $FrontendOut
    throw
}

if (-not (Test-Url $BackendReadyUrl)) {
    throw "Backend was not reachable after startup: $BackendReadyUrl"
}

if (-not (Test-Url $FrontendUrl)) {
    throw "Frontend was not reachable after startup: $FrontendUrl"
}

Write-Host "Voicebox web is running: $FrontendUrl"
Write-Host "Backend API/docs:       $BackendUrl/docs"
Write-Host "Backend port owners:    $(Format-PortOwners $env:VOICEBOX_BACKEND_PORT)"
Write-Host "Frontend port owners:   $(Format-PortOwners $env:VOICEBOX_FRONTEND_PORT)"
