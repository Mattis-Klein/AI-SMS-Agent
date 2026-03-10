Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location "$PSScriptRoot\..\agent"

# Use global Python if .venv doesn't exist
$pythonExe = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $pythonExe = ".venv\Scripts\python.exe"
    & $pythonExe -m pip install -r requirements.txt
}

if (-not $env:AGENT_API_KEY) {
    $envFile = Join-Path (Get-Location) ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*#' -or $line -notmatch '=') {
                continue
            }
            $parts = $line.Split('=', 2)
            if ($parts[0].Trim() -eq 'AGENT_API_KEY' -and $parts[1].Trim()) {
                $env:AGENT_API_KEY = $parts[1].Trim()
                break
            }
        }
    }
}

if (-not $env:AGENT_API_KEY) {
    throw "AGENT_API_KEY is required. Set it in agent/.env or environment before starting."
}

Write-Host "Starting FastAPI Agent on 127.0.0.1:8787..."
Write-Host "API Key: $env:AGENT_API_KEY"
Write-Host ""

& $pythonExe -m uvicorn agent:app --host 127.0.0.1 --port 8787
