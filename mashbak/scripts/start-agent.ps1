Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location "$PSScriptRoot\.."

# Use global Python if .venv doesn't exist
$pythonExe = "python"
if (Test-Path "agent\.venv\Scripts\python.exe") {
    $pythonExe = "agent\.venv\Scripts\python.exe"
    & $pythonExe -m pip install -r "agent\requirements.txt"
}

if (-not $env:AGENT_API_KEY) {
    Write-Host "AGENT_API_KEY is not set in this shell."
    Write-Host "Agent will load it from mashbak/.env.master via ConfigLoader if present."
}

Write-Host "Starting FastAPI Agent on 127.0.0.1:8787..."
Write-Host "API Key: $env:AGENT_API_KEY"
Write-Host ""

& $pythonExe -m uvicorn agent.agent:app --host 127.0.0.1 --port 8787

# Set-StrictMode -Version Latest
# $ErrorActionPreference = 'Stop'

# Set-Location "$PSScriptRoot\..\agent"

# # Use global Python if .venv doesn't exist
# $pythonExe = "python"
# if (Test-Path ".venv\Scripts\python.exe") {
#     $pythonExe = ".venv\Scripts\python.exe"
#     & $pythonExe -m pip install -r requirements.txt
# }

# if (-not $env:AGENT_API_KEY) {
#     Write-Host "AGENT_API_KEY is not set in this shell."
#     Write-Host "Agent will load it from mashbak/.env.master via ConfigLoader if present."
# }

# Write-Host "Starting FastAPI Agent on 127.0.0.1:8787..."
# Write-Host "API Key: $env:AGENT_API_KEY"
# Write-Host ""

# & $pythonExe -m uvicorn agent:app --host 127.0.0.1 --port 8787
