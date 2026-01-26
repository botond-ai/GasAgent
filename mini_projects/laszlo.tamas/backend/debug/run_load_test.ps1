#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Locust load test launcher for Knowledge Router

.DESCRIPTION
    Biztonságos load test futtatás Locust-tal.
    
    KÖVETELMÉNY: pip install locust
    
.PARAMETER Users
    Concurrent users száma (default: 5)
    
.PARAMETER SpawnRate
    User spawn rate (user/sec, default: 1)
    
.PARAMETER Duration
    Teszt időtartama másodpercben (default: 60)
    
.PARAMETER Headless
    Headless mód (nincs Web UI, csak CLI)
    
.EXAMPLE
    .\run_load_test.ps1
    .\run_load_test.ps1 -Users 10 -Duration 120
    .\run_load_test.ps1 -Users 5 -SpawnRate 1 -Headless
#>

param(
    [int]$Users = 5,
    [int]$SpawnRate = 1,
    [int]$Duration = 60,
    [switch]$Headless
)

$ErrorActionPreference = "Stop"

# Colors
$Colors = @{
    Reset = "`e[0m"
    Green = "`e[32m"
    Yellow = "`e[33m"
    Red = "`e[31m"
    Cyan = "`e[36m"
    Bold = "`e[1m"
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "Reset")
    Write-Host "$($Colors[$Color])$Message$($Colors.Reset)"
}

Write-ColorOutput "`n================================================" "Cyan"
Write-ColorOutput "🚀 LOCUST LOAD TEST - KNOWLEDGE ROUTER" "Bold"
Write-ColorOutput "================================================" "Cyan"

# Check if backend is running
Write-ColorOutput "`n🔍 Checking backend availability..." "Yellow"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 5 -ErrorAction Stop
    Write-ColorOutput "✅ Backend is running (Status: $($response.StatusCode))" "Green"
} catch {
    Write-ColorOutput "❌ Backend is NOT running!" "Red"
    Write-ColorOutput "   Start backend first: docker-compose up -d" "Yellow"
    exit 1
}

# Check Locust installation
Write-ColorOutput "`n🔍 Checking Locust installation..." "Yellow"
try {
    $locustVersion = locust --version 2>&1 | Out-String
    if ($locustVersion -match "locust (\d+\.\d+\.\d+)") {
        Write-ColorOutput "✅ Locust is installed (version: $($matches[1]))" "Green"
    } else {
        throw "Locust version check failed"
    }
} catch {
    Write-ColorOutput "❌ Locust is NOT installed!" "Red"
    Write-ColorOutput "   Install: pip install locust" "Yellow"
    exit 1
}

# Display test configuration
Write-ColorOutput "`n📋 Test Configuration:" "Cyan"
Write-ColorOutput "   Target:      http://localhost:8000" "Reset"
Write-ColorOutput "   Users:       $Users" "Reset"
Write-ColorOutput "   Spawn Rate:  $SpawnRate user/sec" "Reset"
Write-ColorOutput "   Duration:    $Duration seconds" "Reset"
Write-ColorOutput "   Mode:        $(if ($Headless) { 'Headless (CLI)' } else { 'Web UI' })" "Reset"

if (-not $Headless) {
    Write-ColorOutput "`n🌐 Web UI will be available at: http://localhost:8089" "Green"
}

Write-ColorOutput "`n⚠️  WARNING: This will send real requests to the backend!" "Yellow"
Write-Host -NoNewLine "Press ENTER to continue or CTRL+C to cancel... "
$null = Read-Host

# Build Locust command
$scriptPath = Join-Path $PSScriptRoot "load_test_chat.py"
$locustArgs = @(
    "-f", $scriptPath,
    "--host=http://localhost:8000"
)

if ($Headless) {
    $locustArgs += @(
        "--headless",
        "--users", $Users,
        "--spawn-rate", $SpawnRate,
        "--run-time", "${Duration}s",
        "--html", "backend/debug/load_test_report.html"
    )
    Write-ColorOutput "`n📊 Report will be saved to: backend/debug/load_test_report.html" "Cyan"
}

Write-ColorOutput "`n🚀 Starting Locust..." "Green"
Write-ColorOutput "================================================`n" "Cyan"

# Run Locust
try {
    & locust @locustArgs
} catch {
    Write-ColorOutput "`n❌ Locust execution failed: $_" "Red"
    exit 1
}

Write-ColorOutput "`n================================================" "Cyan"
Write-ColorOutput "✅ Load test completed!" "Green"
Write-ColorOutput "================================================`n" "Cyan"

if ($Headless) {
    Write-ColorOutput "📊 Open report: backend/debug/load_test_report.html" "Cyan"
}
