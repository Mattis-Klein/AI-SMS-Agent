Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$agentDir = Join-Path $root "agent"
$bridgeDir = Join-Path $root "sms-bridge"

$cloudflaredCmd = "cloudflared"
$cloudflaredArgs = "tunnel --url http://localhost:34567"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    $fallback = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $fallback) {
        $cloudflaredCmd = $fallback
    } else {
        throw "cloudflared not found. Install it or add it to PATH."
    }
}

$processes = @()

function Start-LabeledProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $proc.EnableRaisingEvents = $true

    $null = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
        if ($EventArgs.Data) {
            Write-Host "[$($Event.MessageData.Name)] $($EventArgs.Data)"
        }
    } -MessageData @{ Name = $Name }

    $null = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
        if ($EventArgs.Data) {
            Write-Host "[$($Event.MessageData.Name):ERR] $($EventArgs.Data)"
        }
    } -MessageData @{ Name = $Name }

    $started = $proc.Start()
    if (-not $started) {
        throw "Failed to start $Name"
    }

    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()

    return $proc
}

function Stop-AllProcesses {
    foreach ($p in $processes) {
        if ($p -and -not $p.HasExited) {
            try {
                $p.Kill()
            } catch {
            }
        }
    }
}

try {
    Write-Host "Starting AI-SMS-Agent..."
    Write-Host ""

    if (-not (Test-Path (Join-Path $agentDir ".venv\Scripts\python.exe"))) {
        Write-Host "[setup] Creating Python virtual environment..."
        Push-Location $agentDir
        python -m venv .venv
        Pop-Location
    }

    Write-Host "[setup] Installing Python requirements..."
    & (Join-Path $agentDir ".venv\Scripts\python.exe") -m pip install -r (Join-Path $agentDir "requirements.txt") | Out-Null

    Write-Host "[setup] Installing Node dependencies..."
    Push-Location $bridgeDir
    npm install | Out-Null
    Pop-Location

    $agentPython = Join-Path $agentDir ".venv\Scripts\python.exe"

    $processes += Start-LabeledProcess `
        -Name "agent" `
        -FilePath $agentPython `
        -Arguments "-m uvicorn agent:app --host 127.0.0.1 --port 8787" `
        -WorkingDirectory $agentDir

    Start-Sleep -Seconds 2

    $processes += Start-LabeledProcess `
        -Name "bridge" `
        -FilePath "npm.cmd" `
        -Arguments "start" `
        -WorkingDirectory $bridgeDir

    Start-Sleep -Seconds 2

    $processes += Start-LabeledProcess `
        -Name "tunnel" `
        -FilePath $cloudflaredCmd `
        -Arguments $cloudflaredArgs `
        -WorkingDirectory $root

    Write-Host ""
    Write-Host "AI-SMS-Agent is running."
    Write-Host "Press Ctrl+C to stop everything."
    Write-Host ""

    while ($true) {
        foreach ($p in $processes) {
            if ($p.HasExited) {
                throw "A process exited unexpectedly."
            }
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host ""
    Write-Host "Stopping AI-SMS-Agent..."
    Stop-AllProcesses
    Get-EventSubscriber | Unregister-Event
}