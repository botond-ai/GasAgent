# ===========================
# Knowledge Router - Reset Script (PowerShell)
# ===========================
# This script completely resets the local environment:
# - Stops all containers
# - Removes containers and volumes
# - Starts fresh containers with clean databases

# UTF-8 encoding for console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
chcp 65001 > $null

Write-Host "🔄 Knowledge Router - Environment Reset" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Load ports from .env
$envContent = Get-Content .env -ErrorAction SilentlyContinue
$FRONTEND_PORT = if ($envContent | Select-String "FRONTEND_EXTERNAL_PORT=(\d+)") { ($envContent | Select-String "FRONTEND_EXTERNAL_PORT=(\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) } else { "13000" }
$BACKEND_PORT = if ($envContent | Select-String "BACKEND_EXTERNAL_PORT=(\d+)") { ($envContent | Select-String "BACKEND_EXTERNAL_PORT=(\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) } else { "18000" }
$QDRANT_PORT = if ($envContent | Select-String "QDRANT_HTTP_EXTERNAL_PORT=(\d+)") { ($envContent | Select-String "QDRANT_HTTP_EXTERNAL_PORT=(\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) } else { "16333" }

# Step 1: Stop and remove containers
Write-Host "🛑 Stopping containers..." -ForegroundColor Yellow
docker-compose down

# Step 2: Remove volumes (clean slate)
Write-Host "🗑️  Removing data (this will DELETE all data)..." -ForegroundColor Yellow
Remove-Item -Path "data/postgres/*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "data/qdrant/*" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ Local database files cleared" -ForegroundColor Green

# Step 3: Start fresh
Write-Host ""
Write-Host "✨ Starting fresh environment..." -ForegroundColor Green
docker-compose up -d

# Step 4: Wait for services with health check feedback
Write-Host ""
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Cyan

$maxWaitSeconds = 60
$checkInterval = 2
$elapsed = 0

while ($elapsed -lt $maxWaitSeconds) {
    $backendHealth = docker inspect knowledge_router_backend --format='{{.State.Health.Status}}' 2>$null
    $postgresHealth = docker inspect knowledge_router_postgres --format='{{.State.Health.Status}}' 2>$null
    
    # Show current status
    $postgresStatus = if ($postgresHealth -eq "healthy") { "✅" } elseif ($postgresHealth -eq "starting") { "🔄" } else { "⏳" }
    $backendStatus = if ($backendHealth -eq "healthy") { "✅" } elseif ($backendHealth -eq "starting") { "🔄" } else { "⏳" }
    
    Write-Host "`r  PostgreSQL: $postgresStatus | Backend: $backendStatus | Elapsed: ${elapsed}s   " -NoNewline -ForegroundColor Yellow
    
    # Check if all services are healthy
    if ($postgresHealth -eq "healthy" -and $backendHealth -eq "healthy") {
        Write-Host ""
        Write-Host "✅ All services are healthy!" -ForegroundColor Green
        break
    }
    
    Start-Sleep -Seconds $checkInterval
    $elapsed += $checkInterval
}

if ($elapsed -ge $maxWaitSeconds) {
    Write-Host ""
    Write-Host "⚠️  Timeout reached. Services may still be starting..." -ForegroundColor Yellow
}

# Step 5: Show status
Write-Host ""
Write-Host "✅ Reset complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Container Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "🌐 Access the application:" -ForegroundColor Cyan
Write-Host "   Frontend:    http://localhost:$FRONTEND_PORT" -ForegroundColor White
Write-Host "   Backend API: http://localhost:$BACKEND_PORT" -ForegroundColor White
Write-Host "   Qdrant:      http://localhost:${QDRANT_PORT}/dashboard" -ForegroundColor White
Write-Host ""
Write-Host "📊 Monitoring Stack:" -ForegroundColor Cyan
Write-Host "   Grafana:     http://localhost:3001 (admin/admin)" -ForegroundColor White
Write-Host "   Prometheus:  http://localhost:9090" -ForegroundColor White
Write-Host "   Loki:        http://localhost:3100" -ForegroundColor White
Write-Host "   Tempo:       http://localhost:3200" -ForegroundColor White
Write-Host "   AlertMgr:    http://localhost:9093" -ForegroundColor White
Write-Host ""
Write-Host "📝 Seed data (4 tenants, 3 users) auto-loaded on backend startup" -ForegroundColor Yellow
Write-Host "📄 Sample documents (3 files, 21 chunks) auto-uploaded with embeddings" -ForegroundColor Yellow
