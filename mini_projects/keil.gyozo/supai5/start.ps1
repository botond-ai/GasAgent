# SupportAI Startup Script for Windows
# Run with: .\start.ps1

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  SupportAI v2.0 - Startup Script   " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-Not (Test-Path ".env")) {
    Write-Host "[!] .env file not found!" -ForegroundColor Yellow
    Write-Host "    Creating from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "[!] IMPORTANT: Edit .env and add your OpenAI API key!" -ForegroundColor Red
    Write-Host "    Then run this script again." -ForegroundColor Yellow
    Write-Host ""
    notepad .env
    exit
}

# Check if Docker is running
Write-Host "[*] Checking Docker..." -ForegroundColor Cyan
try {
    docker ps | Out-Null
    Write-Host "[✓] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[✗] Docker is not running!" -ForegroundColor Red
    Write-Host "    Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[*] Starting SupportAI services..." -ForegroundColor Cyan
docker compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[✓] Services started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Waiting for services to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15

    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host "  SupportAI is ready!                " -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Access points:" -ForegroundColor Cyan
    Write-Host "  Frontend UI:       http://localhost:5173" -ForegroundColor White
    Write-Host "  Backend API:       http://localhost:8000" -ForegroundColor White
    Write-Host "  API Docs:          http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  Qdrant Dashboard:  http://localhost:6333/dashboard" -ForegroundColor White
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  View logs:         docker logs supportai-backend -f" -ForegroundColor White
    Write-Host "  Stop services:     docker compose down" -ForegroundColor White
    Write-Host "  Full reset:        docker compose down -v" -ForegroundColor White
    Write-Host ""
    Write-Host "Opening frontend in browser..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:5173"
} else {
    Write-Host ""
    Write-Host "[✗] Failed to start services!" -ForegroundColor Red
    Write-Host "    Check logs with: docker compose logs" -ForegroundColor Yellow
}
