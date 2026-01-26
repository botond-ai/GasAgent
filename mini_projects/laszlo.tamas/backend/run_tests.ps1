# Test runner script for Knowledge Router
# Provides different test modes with appropriate coverage settings

param(
    [string]$Mode = "quick",
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Knowledge Router Test Runner
=============================

Usage: .\run_tests.ps1 [-Mode <mode>]

Modes:
  quick       Run tests without OpenAI, no coverage threshold (default)
  excel       Run only Excel integration tests
  integration Run all integration tests
  full        Run ALL tests with 70% coverage threshold
  unit        Run only unit tests (fast)

Examples:
  .\run_tests.ps1                    # Quick run (no OpenAI, no threshold)
  .\run_tests.ps1 -Mode excel        # Excel tests only
  .\run_tests.ps1 -Mode full         # Full suite with coverage check

"@
    exit 0
}

# Base docker-compose command
$dockerCmd = "docker-compose exec -T -e RUN_OPENAI_TESTS=N backend"

switch ($Mode) {
    "quick" {
        Write-Host "🚀 Quick test run (no OpenAI, no coverage threshold)" -ForegroundColor Cyan
        docker-compose exec -T -e RUN_OPENAI_TESTS=N backend pytest tests/ -v
    }
    
    "excel" {
        Write-Host "📊 Excel integration tests" -ForegroundColor Cyan
        docker-compose exec -T -e RUN_OPENAI_TESTS=N backend pytest tests/integration/test_excel_integration.py -v
    }
    
    "integration" {
        Write-Host "🔗 Integration tests" -ForegroundColor Cyan
        docker-compose exec -T -e RUN_OPENAI_TESTS=N backend pytest tests/integration/ -v -m integration
    }
    
    "unit" {
        Write-Host "⚡ Unit tests (fast)" -ForegroundColor Cyan
        docker-compose exec -T -e RUN_OPENAI_TESTS=N backend pytest tests/unit/ -v -m unit
    }
    
    "full" {
        Write-Host "🎯 FULL test suite with 70% coverage threshold" -ForegroundColor Yellow
        Write-Host "   This will test ALL code and enforce quality standards" -ForegroundColor Yellow
        
        # Full suite with coverage enforcement
        $openaiChoice = Read-Host "Run OpenAI tests? (y/N)"
        $openaiFlag = if ($openaiChoice -match '^[Yy]') { "Y" } else { "N" }
        
        docker-compose exec -T -e RUN_OPENAI_TESTS=$openaiFlag backend pytest tests/ -v --cov-fail-under=70
    }
    
    default {
        Write-Host "❌ Unknown mode: $Mode" -ForegroundColor Red
        Write-Host "   Run with -Help to see available modes" -ForegroundColor Yellow
        exit 1
    }
}

# Check exit code
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Tests failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
