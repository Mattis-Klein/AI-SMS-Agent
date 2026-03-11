Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$bridgeUrl = "http://localhost:34567"

if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
    cloudflared tunnel --url $bridgeUrl
} else {
    $defaultPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (-not (Test-Path $defaultPath)) {
        throw "cloudflared not found. Install Cloudflare Tunnel or add cloudflared to PATH."
    }
    & $defaultPath tunnel --url $bridgeUrl
}
