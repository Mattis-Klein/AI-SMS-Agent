param(
    [switch]$Clean,
    [switch]$OneDir,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = "python"
$entry = Join-Path $repoRoot "desktop_app\main.py"

Push-Location $repoRoot
try {
    if ($Clean) {
        Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue
        Remove-Item -Force "AISMSDesktop.spec" -ErrorAction SilentlyContinue
    }

    & $python -m pip install --upgrade pip | Out-Null
    & $python -m pip install pyinstaller fastapi uvicorn pydantic psutil python-dotenv | Out-Null

    $args = @(
        "--name", "AISMSDesktop",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths", "agent",
        "--paths", "desktop_app",
        "--add-data", "agent/config.json;agent",
        "--add-data", "agent/.env.example;agent",
        "--add-data", "agent/workspace/inbox/.gitkeep;agent/workspace/inbox",
        "--add-data", "agent/workspace/outbox/.gitkeep;agent/workspace/outbox",
        "--add-data", "agent/workspace/logs/.gitkeep;agent/workspace/logs"
    )

    if (-not $OneDir) {
        $args += "--onefile"
    }

    $args += $entry

    if (-not $NoBuild) {
        & $python -m PyInstaller @args
    }

    Write-Host "Build complete."
    if ($OneDir) {
        Write-Host "Output: dist/AISMSDesktop/"
    }
    else {
        Write-Host "Output: dist/AISMSDesktop.exe"
    }
}
finally {
    Pop-Location
}
