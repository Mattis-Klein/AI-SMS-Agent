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
    Remove-Item -Recurse -Force "build\AISMSDesktop" -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force "dist\AISMSDesktop" -ErrorAction SilentlyContinue
    Remove-Item -Force "dist\AISMSDesktop.exe" -ErrorAction SilentlyContinue

    if ($Clean) {
        Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue
        Remove-Item -Force "AISMSDesktop.spec" -ErrorAction SilentlyContinue
        Remove-Item -Force "Mashbak.spec" -ErrorAction SilentlyContinue
    }

    & $python -m pip install --upgrade pip | Out-Null
    & $python -m pip install pyinstaller fastapi uvicorn pydantic psutil python-dotenv | Out-Null

    if (-not $NoBuild) {
        if (-not $OneDir) {
            & $python -m PyInstaller `
                "--name" "Mashbak" `
                "--windowed" `
                "--noconfirm" `
                "--clean" `
                "--paths" "$repoRoot" `
                "--paths" "desktop_app" `
                "--hidden-import" "agent.agent" `
                "--hidden-import" "agent.runtime" `
                "--hidden-import" "imaplib" `
                "--hidden-import" "email" `
                "--hidden-import" "email.policy" `
                "--hidden-import" "email.parser" `
                "--add-data" "agent/config.json;agent" `
                "--add-data" "agent/.env.example;agent" `
                "--add-data" "data/workspace/inbox/.gitkeep;data/workspace/inbox" `
                "--add-data" "data/workspace/outbox/.gitkeep;data/workspace/outbox" `
                "--add-data" "data/workspace/logs/.gitkeep;data/workspace/logs" `
                "--onefile" `
                $entry
        }
        else {
            & $python -m PyInstaller `
                "--name" "Mashbak" `
                "--windowed" `
                "--noconfirm" `
                "--clean" `
                "--paths" "$repoRoot" `
                "--paths" "desktop_app" `
                "--hidden-import" "agent.agent" `
                "--hidden-import" "agent.runtime" `
                "--hidden-import" "imaplib" `
                "--hidden-import" "email" `
                "--hidden-import" "email.policy" `
                "--hidden-import" "email.parser" `
                "--add-data" "agent/config.json;agent" `
                "--add-data" "agent/.env.example;agent" `
                "--add-data" "data/workspace/inbox/.gitkeep;data/workspace/inbox" `
                "--add-data" "data/workspace/outbox/.gitkeep;data/workspace/outbox" `
                "--add-data" "data/workspace/logs/.gitkeep;data/workspace/logs" `
                $entry
        }
    }

    Write-Host "Build complete."
    if ($OneDir) {
        Write-Host "Output: dist/Mashbak/"
    }
    else {
        Write-Host "Output: dist/Mashbak.exe"
    }
}
finally {
    Pop-Location
}
