Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$Phone,
    [switch]$ActivateNow
)

function Normalize-E164 {
    param([string]$Value)

    $rawValue = if ($null -eq $Value) { "" } else { [string]$Value }
    $digits = -join (($rawValue) -replace "\D", "")
    if (-not $digits) {
        throw "Phone number is empty after normalization."
    }

    if ($digits.Length -eq 10) {
        return "+1$digits"
    }
    if ($digits.Length -eq 11 -and $digits.StartsWith("1")) {
        return "+$digits"
    }

    return "+$digits"
}

function Read-JsonFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }
    $raw = Get-Content $Path -Raw
    if (-not $raw.Trim()) {
        return $null
    }
    return $raw | ConvertFrom-Json
}

function Write-JsonFile {
    param(
        [string]$Path,
        [Parameter(Mandatory = $true)]$Object
    )

    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $Object | ConvertTo-Json -Depth 20 | Set-Content -Path $Path
}

function Append-Jsonl {
    param(
        [string]$Path,
        [Parameter(Mandatory = $true)]$Object
    )

    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $line = $Object | ConvertTo-Json -Depth 20 -Compress
    Add-Content -Path $Path -Value $line
}

$platformRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$configPath = Join-Path $platformRoot "assistants\bucherim\config.json"
$usersRoot = Join-Path $platformRoot "data\users\bucherim"
$pendingPath = Join-Path $usersRoot "pending_requests.jsonl"

if (-not (Test-Path $configPath)) {
    throw "Bucherim config not found: $configPath"
}

$normalizedPhone = Normalize-E164 -Value $Phone
$userKey = "p" + (($normalizedPhone -replace "\D", ""))
$userDir = Join-Path $usersRoot $userKey
$membershipPath = Join-Path $userDir "membership.json"
$requestsPath = Join-Path $userDir "requests.jsonl"

$config = Read-JsonFile -Path $configPath
if (-not $config) {
    throw "Invalid Bucherim config JSON: $configPath"
}

if (-not $config.allowlist) {
    $config | Add-Member -NotePropertyName allowlist -NotePropertyValue @()
}

$allowlist = @($config.allowlist)
if ($allowlist -notcontains $normalizedPhone) {
    $allowlist += $normalizedPhone
}
$config.allowlist = $allowlist
Write-JsonFile -Path $configPath -Object $config

$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$status = if ($ActivateNow) { "active" } else { "allowed_not_joined" }
$source = "approved_request"

if (Test-Path $membershipPath) {
    $membership = Read-JsonFile -Path $membershipPath
    if (-not $membership) {
        $membership = @{}
    }

    $membership.phone_number = $normalizedPhone
    $membership.status = $status
    $membership.source = $source
    if ($ActivateNow -and -not $membership.joined_at) {
        $membership.joined_at = $now
    }
    if (-not $membership.PSObject.Properties.Name.Contains("history")) {
        $membership | Add-Member -NotePropertyName history -NotePropertyValue @()
    }

    $membershipEvent = [ordered]@{
        timestamp = $now
        event = if ($ActivateNow) { "approved_and_activated" } else { "approved_allowlisted" }
        status = $status
        phone_number = $normalizedPhone
        details = @{ source = $source }
    }

    $history = @($membership.history)
    $history += $membershipEvent
    $membership.history = $history
    $membership.updated_at = $now

    Write-JsonFile -Path $membershipPath -Object $membership
    Append-Jsonl -Path (Join-Path $userDir "conversation.jsonl") -Object ([ordered]@{
        timestamp = $now
        direction = "event"
        event_type = "membership"
        event = $membershipEvent.event
        status = $status
        details = $membershipEvent.details
    })
}

if (Test-Path $pendingPath) {
    $lines = Get-Content $pendingPath | Where-Object { $_.Trim() }
    $kept = @()
    foreach ($line in $lines) {
        try {
            $entry = $line | ConvertFrom-Json
            if ($entry.phone_number -ne $normalizedPhone) {
                $kept += $line
            }
        } catch {
            $kept += $line
        }
    }
    Set-Content -Path $pendingPath -Value $kept
}

if (Test-Path $requestsPath) {
    Append-Jsonl -Path $requestsPath -Object ([ordered]@{
        timestamp = $now
        phone_number = $normalizedPhone
        status = $status
        review_state = "approved"
        approved_source = $source
    })
}

Write-Host "Approved Bucherim member: $normalizedPhone"
Write-Host "Updated allowlist: $configPath"
Write-Host "Membership status: $status"
