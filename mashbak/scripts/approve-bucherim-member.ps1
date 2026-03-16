Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$Phone,
    [switch]$ActivateNow
)

function Convert-ToE164 {
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

function Add-JsonlRecord {
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

function New-ExclusiveLock {
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
$approvedNumbersPath = Join-Path $platformRoot "assistants\bucherim\config\approved_numbers.json"
$newPendingPath = Join-Path $platformRoot "assistants\bucherim\config\pending_requests.json"
$usersRoot = Join-Path $platformRoot "data\users\bucherim"
$pendingPath = Join-Path $usersRoot "pending_requests.jsonl"
$mutationLockPath = Join-Path $platformRoot "assistants\bucherim\config\.approve-member.lock"

$normalizedPhone = Convert-ToE164 -Value $Phone
$userKey = "p" + (($normalizedPhone -replace "\D", ""))
$userDir = Join-Path $usersRoot $userKey
$membershipPath = Join-Path $userDir "membership.json"
$requestsPath = Join-Path $userDir "requests.jsonl"

$lockHandle = $null
$rollbackTargets = @{}

try {
    # Serialize multi-file mutation to avoid races across concurrent approvals.
    $lockHandle = New-ExclusiveLock -LockPath $mutationLockPath

    $pathsToTrack = @($approvedNumbersPath, $newPendingPath, $membershipPath, $pendingPath)
    foreach ($path in $pathsToTrack) {
        $exists = Test-Path $path
        $rollbackTargets[$path] = [ordered]@{
            existed = $exists
            raw = if ($exists) { Get-Content -Path $path -Raw } else { $null }
        }
    }

    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $source = "approved_request"

    $membership = Read-JsonFile -Path $membershipPath
    $status = "approved"

    if (-not $membership) {
        $membership = [ordered]@{
            phone_number = $normalizedPhone
            status = $status
            source = $source
            joined_at = if ($ActivateNow) { $now } else { $null }
            updated_at = $now
            history = @()
        }
    } else {
        $membership.phone_number = $normalizedPhone
        $membership.status = $status
        $membership.source = $source
        if ($ActivateNow -and -not $membership.joined_at) {
            $membership.joined_at = $now
        }
        if (-not ($membership.PSObject.Properties.Name -contains "history")) {
            $membership | Add-Member -NotePropertyName history -NotePropertyValue @()
        }
    }

    $membershipEvent = [ordered]@{
        timestamp = $now
        event = if ($ActivateNow) { "approved_and_activated" } else { "approved" }
        status = $status
        phone_number = $normalizedPhone
        details = @{ source = $source }
    }

    $history = @($membership.history)
    $history += $membershipEvent
    $membership.history = $history
    $membership.updated_at = $now

    Write-JsonFile -Path $membershipPath -Object $membership

    # Also write to the new canonical approved_numbers.json.
    $approvedNumbers = @()
    if (Test-Path $approvedNumbersPath) {
        $rawApproved = Read-JsonFile -Path $approvedNumbersPath
        if ($rawApproved -and $rawApproved.PSObject.Properties.Name -contains "numbers") {
            $approvedNumbers = @($rawApproved.numbers)
        }
    }
    if ($approvedNumbers -notcontains $normalizedPhone) {
        $approvedNumbers += $normalizedPhone
    }
    $approvedNumbersDir = Split-Path -Parent $approvedNumbersPath
    if (-not (Test-Path $approvedNumbersDir)) {
        New-Item -ItemType Directory -Path $approvedNumbersDir -Force | Out-Null
    }
    Write-JsonFile -Path $approvedNumbersPath -Object ([ordered]@{ numbers = @($approvedNumbers | Sort-Object) })

    Add-JsonlRecord -Path (Join-Path $userDir "conversation.jsonl") -Object ([ordered]@{
        timestamp = $now
        direction = "event"
        event_type = "membership"
        event = $membershipEvent.event
        status = $status
        details = $membershipEvent.details
    })

    # Remove from legacy pending_requests.jsonl.
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

    # Remove from new canonical pending_requests.json.
    if (Test-Path $newPendingPath) {
        $rawPending = Read-JsonFile -Path $newPendingPath
        $pendingRequests = if ($rawPending -and $rawPending.PSObject.Properties.Name -contains "requests") { @($rawPending.requests) } else { @() }
        $filteredRequests = @($pendingRequests | Where-Object {
            $null -ne $_ -and $_.PSObject.Properties.Name -contains "phone_number" -and $_.phone_number -ne $normalizedPhone
        })
        Write-JsonFile -Path $newPendingPath -Object ([ordered]@{ requests = $filteredRequests })
    }

    Add-JsonlRecord -Path $requestsPath -Object ([ordered]@{
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
Write-Host "Updated approved_numbers: $approvedNumbersPath"
Write-Host "Membership status: $status"
