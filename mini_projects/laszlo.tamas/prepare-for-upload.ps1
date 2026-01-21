# ===========================
# Knowledge Router - Prepare for Upload Script (PowerShell)
# ===========================
# This script prepares the codebase for uploading to instructor repository:
# - Stops all containers
# - Removes containers and volumes
# - Cleans all data directories
# - Does NOT restart (ready for commit/upload)

# UTF-8 encoding for console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
chcp 65001 > $null

Write-Host "📦 Knowledge Router - Prepare for Upload" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop and remove containers
Write-Host "🛑 Stopping all containers..." -ForegroundColor Yellow
docker-compose down --volumes --remove-orphans

Write-Host "🧹 Removing Docker volumes..." -ForegroundColor Yellow  
docker volume prune -f

Write-Host "🗑️ Removing Docker networks..." -ForegroundColor Yellow
docker network prune -f

# Step 2: Clean all data directories
Write-Host ""
Write-Host "🗂️ Cleaning data directories..." -ForegroundColor Yellow

$dataDirectories = @(
    "data/excel_files",
    "data/postgres", 
    "data/qdrant"
)

foreach ($dir in $dataDirectories) {
    if (Test-Path $dir) {
        Write-Host "   Cleaning: $dir" -ForegroundColor White
        Remove-Item -Path "$dir/*" -Recurse -Force -ErrorAction SilentlyContinue
        # Keep the directory structure but clean contents
        if (Test-Path "$dir") {
            Write-Host "   ✅ $dir cleaned" -ForegroundColor Green
        }
    } else {
        Write-Host "   ℹ️ $dir not found (OK)" -ForegroundColor Gray
    }
}

# Step 3: Clean additional development files
Write-Host ""
Write-Host "🧽 Cleaning development artifacts..." -ForegroundColor Yellow

$cleanupPaths = @(
    "backend/__pycache__",
    "backend/*/__pycache__", 
    "backend/*/*/__pycache__",
    "backend/*/*/*/__pycache__",
    "backend/.pytest_cache",
    "backend/htmlcov",
    "backend/coverage.xml",
    "backend/*.log",
    "backend/*/*.log",
    "frontend/node_modules",
    "frontend/dist",
    "frontend/.next",
    "*.tmp",
    "*.temp",
    ".DS_Store",
    "Thumbs.db"
)

foreach ($pattern in $cleanupPaths) {
    $items = Get-ChildItem -Path $pattern -Recurse -ErrorAction SilentlyContinue
    if ($items) {
        foreach ($item in $items) {
            Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "   Removed: $($item.Name)" -ForegroundColor White
        }
    }
}

# Step 4: Verify .env is not committed (should be .env.example only)
Write-Host ""
Write-Host "🔒 Verifying sensitive files..." -ForegroundColor Yellow

if (Test-Path ".env") {
    Write-Host "   ⚠️  .env file found - ensure it's in .gitignore!" -ForegroundColor Yellow
    Write-Host "      (Contains API keys, should not be committed)" -ForegroundColor Gray
} else {
    Write-Host "   ✅ .env file not present (good for upload)" -ForegroundColor Green
}

if (Test-Path ".env.example") {
    Write-Host "   ✅ .env.example present (template file)" -ForegroundColor Green
} else {
    Write-Host "   ❌ .env.example missing! This should exist for students." -ForegroundColor Red
}

# Step 5: Show current status
Write-Host ""
Write-Host "📊 Current directory structure:" -ForegroundColor Cyan
Get-ChildItem -Directory | Where-Object { $_.Name -notmatch "node_modules|__pycache__|\.git" } | ForEach-Object {
    Write-Host "   📁 $($_.Name)" -ForegroundColor White
}

Write-Host ""
Write-Host "✅ Cleanup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Ready for upload checklist:" -ForegroundColor Cyan
Write-Host "   ✅ Containers stopped" -ForegroundColor Green
Write-Host "   ✅ Data directories cleaned" -ForegroundColor Green
Write-Host "   ✅ Development artifacts removed" -ForegroundColor Green
Write-Host "   ✅ Docker resources pruned" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 The codebase is now ready for instructor repository upload!" -ForegroundColor Green
Write-Host "📝 Remember to verify .gitignore includes sensitive files." -ForegroundColor Yellow
Write-Host ""