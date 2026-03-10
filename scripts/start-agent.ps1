Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location "$PSScriptRoot\..\agent"

# Use global Python if .venv doesn't exist
$pythonExe = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $pythonExe = ".venv\Scripts\python.exe"
    & $pythonExe -m pip install -r requirements.txt
}

$env:AGENT_API_KEY = if ($env:AGENT_API_KEY) { $env:AGENT_API_KEY } else { "local-dev-key" }

Write-Host "Starting FastAPI Agent on 127.0.0.1:8787..."
Write-Host "API Key: $env:AGENT_API_KEY"
Write-Host ""

& $pythonExe -m uvicorn agent:app --host 127.0.0.1 --port 8787
