# Reset PostgreSQL and Qdrant Databases
Write-Host "=== Database Reset ===" -ForegroundColor Cyan
Write-Host ""

# PostgreSQL Reset
Write-Host "[1] Resetting PostgreSQL..." -ForegroundColor Yellow

$pgReset = @"
-- Delete all document chunks
DELETE FROM document_chunks;
-- Delete all documents
DELETE FROM documents;
-- Reset sequences
ALTER SEQUENCE documents_id_seq RESTART WITH 1;
ALTER SEQUENCE document_chunks_id_seq RESTART WITH 1;
"@

# Save SQL script
$pgReset | Out-File -FilePath "temp_reset.sql" -Encoding UTF8

# Execute via docker
try {
    docker exec -i ai_chat_phase2-backend-1 psql -h viaduct.proxy.rlwy.net -p 14220 -U postgres -d railway -c "DELETE FROM document_chunks; DELETE FROM documents;"
    Write-Host "✅ PostgreSQL reset complete" -ForegroundColor Green
} catch {
    Write-Host "❌ PostgreSQL reset failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "[2] Resetting Qdrant..." -ForegroundColor Yellow

# Qdrant - delete all points from collection
try {
    $qdrantBody = @{
        filter = @{
            must = @(
                @{
                    key = "tenant_id"
                    match = @{
                        any = @(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
                    }
                }
            )
        }
    } | ConvertTo-Json -Depth 10

    # Get Qdrant credentials from backend
    $qdrantUrl = "https://2b0997df-4157-427e-b90d-bf6e6df2d1f4.europe-west3-0.gcp.cloud.qdrant.io:6333"
    $collection = "r_d_ai_chat_document_chunks"
    
    # Try to delete points
    Invoke-RestMethod -Uri "$qdrantUrl/collections/$collection/points/delete" `
        -Method POST `
        -Headers @{
            "Content-Type" = "application/json"
        } `
        -Body $qdrantBody
    
    Write-Host "✅ Qdrant reset complete" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Qdrant reset failed (may require API key): $_" -ForegroundColor Yellow
    Write-Host "   Attempting alternative method via backend..." -ForegroundColor Gray
    
    # Alternative: use backend endpoint to clear Qdrant
    try {
        $result = Invoke-RestMethod -Uri "http://localhost:8000/api/debug/qdrant/clear" -Method POST
        Write-Host "✅ Qdrant cleared via backend endpoint" -ForegroundColor Green
    } catch {
        Write-Host "❌ Could not clear Qdrant: $_" -ForegroundColor Red
    }
}

# Cleanup
if (Test-Path "temp_reset.sql") {
    Remove-Item "temp_reset.sql"
}

Write-Host ""
Write-Host "=== Reset Complete ===" -ForegroundColor Cyan
Write-Host "Verify by checking document count:" -ForegroundColor White
Write-Host "  docker exec ai_chat_phase2-backend-1 psql -h viaduct.proxy.rlwy.net -p 14220 -U postgres -d railway -c 'SELECT COUNT(*) FROM documents;'" -ForegroundColor Gray
