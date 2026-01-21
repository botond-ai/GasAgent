#!/usr/bin/env pwsh
# Test Cache Control - Runtime API Architecture

Write-Host "`n=== Cache Control - Runtime API Test ===" -ForegroundColor Cyan

Write-Host "`n[INFO] Architecture: Frontend fetches DEV_MODE from backend at runtime" -ForegroundColor Yellow
Write-Host "   [OK] No build-time dependency"
Write-Host "   [OK] Single source of truth (system.ini)"
Write-Host "   [OK] No rebuild needed for cache config change"

Write-Host "`n[1] Testing Backend Endpoint" -ForegroundColor Green
$devMode = curl.exe -s http://localhost:8000/api/config/dev-mode | ConvertFrom-Json
Write-Host "   GET /api/config/dev-mode → dev_mode: $($devMode.dev_mode)"

if ($devMode.dev_mode -eq $false) {
    Write-Host "   [OK] DEV_MODE=false (caches ENABLED)" -ForegroundColor Green
} else {
    Write-Host "   [WARN] DEV_MODE=true (caches DISABLED)" -ForegroundColor Yellow
}

Write-Host "`n[2] Testing Cache Stats" -ForegroundColor Green
$stats = curl.exe -s http://localhost:8000/api/admin/cache/stats | ConvertFrom-Json
Write-Host "   Memory cache enabled: $($stats.memory_cache.enabled)"
Write-Host "   Memory cache size: $($stats.memory_cache.size)"
Write-Host "   DB cache enabled: $($stats.db_cache.enabled)"

Write-Host "`n[3] Testing Cache Behavior" -ForegroundColor Green
Write-Host "   Fetching tenants (1st call)..."
$start1 = Get-Date
$tenants1 = curl.exe -s http://localhost:8000/api/tenants | ConvertFrom-Json
$duration1 = ((Get-Date) - $start1).TotalMilliseconds
Write-Host "   Duration: $([math]::Round($duration1, 2))ms (Cache MISS expected)"

Start-Sleep -Milliseconds 100

Write-Host "   Fetching tenants (2nd call)..."
$start2 = Get-Date
$tenants2 = curl.exe -s http://localhost:8000/api/tenants | ConvertFrom-Json
$duration2 = ((Get-Date) - $start2).TotalMilliseconds
Write-Host "   Duration: $([math]::Round($duration2, 2))ms (Cache HIT expected)"

if ($duration2 -lt $duration1) {
    Write-Host "   [OK] Cache working! (2nd call faster)" -ForegroundColor Green
} else {
    Write-Host "   [WARN] Cache might be disabled (2nd call not faster)" -ForegroundColor Yellow
}

Write-Host "`n[4] Frontend Test" -ForegroundColor Green
Write-Host "   => Open http://localhost:3000 in browser"
Write-Host "   => Open Developer Tools (F12) -> Console"
Write-Host "   => Look for: [Dev mode] from system.ini: false"
Write-Host "   => Go to Network tab -> Check /api/tenants request headers"

Write-Host "`n[RESULTS] Expected Results:" -ForegroundColor Cyan
Write-Host "   DEV_MODE=false:"
Write-Host "     - Backend: Fast cache responses (<1ms on repeated calls)"
Write-Host "     - Frontend: NO Cache-Control header in API requests"
Write-Host "   DEV_MODE=true:"
Write-Host "     - Backend: All DB queries (no cache)"
Write-Host "     - Frontend: Cache-Control: no-cache, no-store, must-revalidate"

Write-Host "`n[CHANGE] To test DEV_MODE=true:" -ForegroundColor Yellow
Write-Host "   1. Edit backend/config/system.ini → DEV_MODE=true"
Write-Host "   2. docker-compose restart backend"
Write-Host "   3. Refresh browser (Frontend auto-detects new setting!)"
Write-Host "   4. Run this script again"

Write-Host "`n[OK] Test Complete!" -ForegroundColor Green
