# SupportAI Stop Script for Windows
# Run with: .\stop.ps1

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  SupportAI v2.0 - Stop Script       " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[*] Stopping SupportAI services..." -ForegroundColor Cyan
docker compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[✓] Services stopped successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To start again: .\start.ps1" -ForegroundColor Cyan
    Write-Host "To reset data:  docker compose down -v" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "[✗] Failed to stop services!" -ForegroundColor Red
}
