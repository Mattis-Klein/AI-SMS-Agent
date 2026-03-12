# Test Script for AI-SMS-Agent Improvements
# This script verifies that the enhanced features are working correctly.

Write-Host "Testing AI-SMS-Agent Improvements..." -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Continue"
$testsPassed = 0
$testsFailed = 0

function Pass([string]$msg) {
    Write-Host "  [PASS] $msg" -ForegroundColor Green
    $script:testsPassed++
}

function Fail([string]$msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    $script:testsFailed++
}

Write-Host "[Test 1] Checking config.json..." -ForegroundColor Yellow
if (Test-Path "agent\config.json") {
    Pass "config.json exists"
    try {
        $config = Get-Content "agent\config.json" -Raw | ConvertFrom-Json
        Pass "config.json is valid JSON"
        $count = $config.allowed_commands.PSObject.Properties.Count
        Pass "Found $count commands in whitelist"
    } catch {
        Fail "config.json has invalid JSON"
    }
} else {
    Fail "config.json not found"
}

Write-Host ""
Write-Host "[Test 2] Checking agent.py enhancements..." -ForegroundColor Yellow
$agentContent = Get-Content "agent\agent.py" -Raw
if ($agentContent -match "FastAPI" -and $agentContent -match "execute_tool" -and $agentContent -match "execute_natural_language") {
    Pass "agent.py has FastAPI endpoints"
} else {
    Fail "agent.py is missing expected FastAPI endpoints"
}
if ($agentContent -match "x_sender" -and $agentContent -match "x-api-key") {
    Pass "agent.py implements authentication and sender logging"
} else {
    Fail "agent.py missing authentication or sender logging"
}

Write-Host ""
Write-Host "[Test 3] Checking requirements.txt..." -ForegroundColor Yellow
$requirements = Get-Content "agent\requirements.txt" -Raw
if ($requirements -match "psutil") {
    Pass "psutil is present in requirements"
} else {
    Fail "psutil missing from requirements"
}

Write-Host ""
Write-Host "[Test 4] Checking sms_bridge updates..." -ForegroundColor Yellow
if (Test-Path "sms_bridge\sms-server.js") {
    $bridgeContent = Get-Content "sms_bridge\sms-server.js" -Raw
    if ($bridgeContent -match "express" -and $bridgeContent -match "app.post") {
        Pass "bridge has Express endpoints"
    } else {
        Fail "bridge missing expected endpoint structure"
    }
} else {
    Fail "sms_bridge/sms-server.js not found"
}

Write-Host ""
Write-Host "[Test 5] Checking workspace structure..." -ForegroundColor Yellow
$directories = @(
    "data\workspace\inbox",
    "data\workspace\outbox",
    "data\workspace\logs",
    "data\logs"
)
foreach ($dir in $directories) {
    if (Test-Path $dir) {
        Pass "$dir exists"
    } else {
        Fail "$dir missing"
    }
}

Write-Host ""
Write-Host "[Test 6] Checking git repository..." -ForegroundColor Yellow
if (Test-Path ".git") {
    Pass "git repository initialized"
    try {
        $commitLines = @(git log --oneline)
        Pass "Found $($commitLines.Count) commit(s)"
    } catch {
        Pass "git repository exists (commit count unavailable)"
    }
} else {
    Fail "git repository not initialized"
}

Write-Host ""
Write-Host "[Test 7] Checking documentation..." -ForegroundColor Yellow
$docs = @(
    "README.md",
    "docs\COMMANDS.md",
    "docs\WHITELIST-SECURITY.md"
)
foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Pass "$doc exists"
    } else {
        Fail "$doc missing"
    }
}

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Test Results:" -ForegroundColor Cyan
Write-Host "  Passed: $testsPassed" -ForegroundColor Green
if ($testsFailed -eq 0) {
    Write-Host "  Failed: $testsFailed" -ForegroundColor Green
} else {
    Write-Host "  Failed: $testsFailed" -ForegroundColor Red
}
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "All tests passed. System is ready." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Configure mashbak/.env.master"
    Write-Host "  2. Test locally: .\scripts\dev-start.ps1"
    Write-Host "  3. Push to GitHub:"
    Write-Host "     git remote add origin https://github.com/mattis-Klein/AI-SMS-Agent.git"
    Write-Host "     git branch -M main"
    Write-Host "     git push -u origin main"
} else {
    Write-Host "Some tests failed. Review messages above." -ForegroundColor Red
    exit 1
}
