#!/usr/bin/env pwsh
# Test frontend Cache-Control headers

Write-Host "`n=== Frontend Cache-Control Header Test ===" -ForegroundColor Cyan

Write-Host "`n📋 Test Setup:" -ForegroundColor Yellow
Write-Host "  - VITE_DEV_MODE should be in .env (false by default)"
Write-Host "  - Frontend sends Cache-Control header if VITE_DEV_MODE=true"
Write-Host "  - We'll test by checking browser dev tools or proxy"

Write-Host "`n1️⃣ Opening browser to http://localhost:3000" -ForegroundColor Green
Write-Host "   👉 Open Developer Tools (F12)"
Write-Host "   👉 Go to Network tab"
Write-Host "   👉 Refresh page"
Write-Host "   👉 Check request headers for /api/tenants call"

Write-Host "`n2️⃣ Expected behavior:" -ForegroundColor Green
Write-Host "   - VITE_DEV_MODE=false (default): NO Cache-Control header in requests"
Write-Host "   - VITE_DEV_MODE=true: Cache-Control: no-cache, no-store, must-revalidate"

Write-Host "`n3️⃣ To test with DEV_MODE enabled:" -ForegroundColor Green
Write-Host "   1. Add to .env: VITE_DEV_MODE=true"
Write-Host "   2. docker-compose build frontend"
Write-Host "   3. docker-compose up -d frontend"
Write-Host "   4. Check browser Network tab again"

Write-Host "`n✅ Opening browser..." -ForegroundColor Green
Start-Process "http://localhost:3000"

Write-Host "`nℹ️  Manual verification required - check browser Network tab!" -ForegroundColor Cyan
