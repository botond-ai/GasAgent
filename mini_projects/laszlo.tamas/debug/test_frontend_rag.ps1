# Test Frontend RAG Integration
Write-Host "=== Frontend RAG Integration Test ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Backend RAG endpoint
Write-Host "[Test 1] Backend RAG endpoint test..." -ForegroundColor Yellow
$ragRequest = @{
    user_id = 1
    tenant_id = 1
    query = "What is in document 9?"
} | ConvertTo-Json

try {
    $ragResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/chat/rag" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body $ragRequest
    
    Write-Host "✅ Backend RAG response:" -ForegroundColor Green
    Write-Host "  Answer: $($ragResponse.answer.Substring(0, [Math]::Min(80, $ragResponse.answer.Length)))..." -ForegroundColor Gray
    Write-Host "  Sources: $($ragResponse.sources -join ', ')" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Host "❌ Backend test failed: $_" -ForegroundColor Red
}

# Test 2: Frontend availability
Write-Host "[Test 2] Frontend availability..." -ForegroundColor Yellow
try {
    $frontendResponse = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing
    if ($frontendResponse.StatusCode -eq 200) {
        Write-Host "✅ Frontend accessible at http://localhost:3000" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Frontend not accessible: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Manual Test Instructions ===" -ForegroundColor Cyan
Write-Host "1. Open http://localhost:3000 in browser" -ForegroundColor White
Write-Host "2. Select Tenant and User from dropdowns" -ForegroundColor White
Write-Host "3. Ask a question about your uploaded documents" -ForegroundColor White
Write-Host "4. Check if answer includes source badges" -ForegroundColor White
Write-Host ""
Write-Host "Example query: What is in the test document?" -ForegroundColor Yellow
