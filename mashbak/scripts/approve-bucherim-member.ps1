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
    $Object | ConvertTo-Json -Depth 20 | Set-Content -Path $Path -Encoding UTF8
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
    Add-Content -Path $Path -Value $line -Encoding UTF8
}

function Acquire-ExclusiveLock {
    param([Parameter(Mandatory = $true)][string]$LockPath)

    $dir = Split-Path -Parent $LockPath
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $lockStream = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $lockStream.SetLength(0)
    $lockBytes = [System.Text.Encoding]::UTF8.GetBytes("pid=$PID utc=$([DateTime]::UtcNow.ToString('o'))")
    $lockStream.Write($lockBytes, 0, $lockBytes.Length)
    $lockStream.Flush()
    return $lockStream
}

function Restore-OriginalContent {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowNull()]$OriginalRaw,
        [bool]$ExistedBefore
    )

    if ($ExistedBefore) {
        if ($null -eq $OriginalRaw) {
            Set-Content -Path $Path -Value "" -Encoding UTF8
        } else {
            Set-Content -Path $Path -Value $OriginalRaw -Encoding UTF8
        }
    } elseif (Test-Path $Path) {
        Remove-Item -Path $Path -Force
    }
}

$platformRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$configPath = Join-Path $platformRoot "assistants\bucherim\config.json"
$usersRoot = Join-Path $platformRoot "data\users\bucherim"
$pendingPath = Join-Path $usersRoot "pending_requests.jsonl"
$mutationLockPath = Join-Path $usersRoot ".approve-member.lock"

if (-not (Test-Path $configPath)) {
    throw "Bucherim config not found: $configPath"
}

$normalizedPhone = Normalize-E164 -Value $Phone
$userKey = "p" + (($normalizedPhone -replace "\D", ""))
$userDir = Join-Path $usersRoot $userKey
$membershipPath = Join-Path $userDir "membership.json"
$requestsPath = Join-Path $userDir "requests.jsonl"

$lockHandle = $null
$rollbackTargets = @{}

try {
    # Serialize multi-file mutation to avoid races across concurrent approvals.
    $lockHandle = Acquire-ExclusiveLock -LockPath $mutationLockPath

    $pathsToTrack = @($configPath, $membershipPath, $pendingPath)
    foreach ($path in $pathsToTrack) {
        $exists = Test-Path $path
        $rollbackTargets[$path] = [ordered]@{
            existed = $exists
            raw = if ($exists) { Get-Content -Path $path -Raw } else { $null }
        }
    }

    $config = Read-JsonFile -Path $configPath
    if (-not $config) {
        throw "Invalid Bucherim config JSON: $configPath"
    }

    if (-not ($config.PSObject.Properties.Name -contains "allowlist")) {
        $config | Add-Member -NotePropertyName allowlist -NotePropertyValue @()
    }

    $allowlist = if ($null -eq $config.allowlist) { @() } else { @($config.allowlist) }
    if ($allowlist -notcontains $normalizedPhone) {
        $allowlist += $normalizedPhone
    }
    $config.allowlist = $allowlist

    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $source = "approved_request"

    $membership = Read-JsonFile -Path $membershipPath
    $existingStatus = if ($membership -and ($membership.PSObject.Properties.Name -contains "status")) { [string]$membership.status } else { "" }
    $status = if ($ActivateNow) {
        "active"
    } elseif ($existingStatus -eq "active") {
        "active"
    } else {
        "allowlisted"
    }

    if (-not $membership) {
        $membership = [ordered]@{
            phone_number = $normalizedPhone
            status = $status
            source = $source
            joined_at = if ($status -eq "active") { $now } else { $null }
            updated_at = $now
            history = @()
        }
    } else {
        $membership.phone_number = $normalizedPhone
        $membership.status = $status
        $membership.source = $source
        if ($status -eq "active" -and -not $membership.joined_at) {
            $membership.joined_at = $now
        }
        if (-not ($membership.PSObject.Properties.Name -contains "history")) {
            $membership | Add-Member -NotePropertyName history -NotePropertyValue @()
        }
    }

    $membershipEvent = [ordered]@{
        timestamp = $now
        event = if ($status -eq "active") { "approved_and_activated" } else { "approved_allowlisted" }
        status = $status
        phone_number = $normalizedPhone
        details = @{ source = $source }
    }

    $history = @($membership.history)
    $history += $membershipEvent
    $membership.history = $history
    $membership.updated_at = $now

    Write-JsonFile -Path $membershipPath -Object $membership
    Write-JsonFile -Path $configPath -Object $config

    Append-Jsonl -Path (Join-Path $userDir "conversation.jsonl") -Object ([ordered]@{
        timestamp = $now
        direction = "event"
        event_type = "membership"
        event = $membershipEvent.event
        status = $status
        details = $membershipEvent.details
    })

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
        Set-Content -Path $pendingPath -Value $kept -Encoding UTF8
    }

    Append-Jsonl -Path $requestsPath -Object ([ordered]@{
        timestamp = $now
        phone_number = $normalizedPhone
        status = $status
        review_state = "approved"
        approved_source = $source
    })
}
catch {
    foreach ($path in $rollbackTargets.Keys) {
        $snapshot = $rollbackTargets[$path]
        Restore-OriginalContent -Path $path -OriginalRaw $snapshot.raw -ExistedBefore ([bool]$snapshot.existed)
    }
    throw
}
finally {
    if ($lockHandle) {
        $lockHandle.Dispose()
    }
}

Write-Host "Approved Bucherim member: $normalizedPhone"
Write-Host "Updated allowlist: $configPath"
Write-Host "Membership status: $status"
