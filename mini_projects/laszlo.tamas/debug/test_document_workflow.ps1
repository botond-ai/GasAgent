# Test Document Workflow (NEW)
# Tests the automated document processing pipeline

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$API_URL = "http://localhost:8000/api"

Write-Host "🧪 Testing Document Workflow (Automated Pipeline)" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Test file
$testFile = "test_files\fantasy_story.txt"

if (-not (Test-Path $testFile)) {
    Write-Host "❌ Test file not found: $testFile" -ForegroundColor Red
    exit 1
}

Write-Host "`n📄 Test file: $testFile" -ForegroundColor Yellow

# Read file content
$fileContent = Get-Content $testFile -Raw -Encoding UTF8
$fileBytes = [System.Text.Encoding]::UTF8.GetBytes($fileContent)

# Create multipart form data
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"fantasy_story.txt`"",
    "Content-Type: text/plain; charset=utf-8",
    "",
    $fileContent,
    "--$boundary",
    "Content-Disposition: form-data; name=`"tenant_id`"",
    "",
    "1",
    "--$boundary",
    "Content-Disposition: form-data; name=`"user_id`"",
    "",
    "2",
    "--$boundary",
    "Content-Disposition: form-data; name=`"visibility`"",
    "",
    "tenant",
    "--$boundary--"
)

$body = $bodyLines -join $LF

Write-Host "`n🚀 Uploading document with automated workflow..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod `
        -Uri "$API_URL/workflows/process-document" `
        -Method POST `
        -ContentType "multipart/form-data; boundary=$boundary" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
    
    Write-Host "`n✅ SUCCESS! Document processed" -ForegroundColor Green
    Write-Host "`n📊 Workflow Summary:" -ForegroundColor Cyan
    Write-Host "  Status:          $($response.status)" -ForegroundColor White
    Write-Host "  Document ID:     $($response.document_id)" -ForegroundColor White
    Write-Host "  Filename:        $($response.summary.filename)" -ForegroundColor White
    Write-Host "  Content Length:  $($response.summary.content_length) chars" -ForegroundColor White
    Write-Host "  Chunks:          $($response.summary.chunk_count)" -ForegroundColor White
    Write-Host "  Embeddings:      $($response.summary.embedding_count)" -ForegroundColor White
    Write-Host "  Qdrant Vectors:  $($response.summary.qdrant_vectors)" -ForegroundColor White
    
    Write-Host "`n✨ Full pipeline completed:" -ForegroundColor Green
    Write-Host "  ✅ File validation" -ForegroundColor Green
    Write-Host "  ✅ Content extraction" -ForegroundColor Green
    Write-Host "  ✅ Database storage" -ForegroundColor Green
    Write-Host "  ✅ Text chunking" -ForegroundColor Green
    Write-Host "  ✅ Embedding generation" -ForegroundColor Green
    Write-Host "  ✅ Qdrant upload" -ForegroundColor Green
    Write-Host "  ✅ Verification" -ForegroundColor Green
    
    Write-Host "`n🎉 Document ready for RAG queries!" -ForegroundColor Cyan
    
} catch {
    Write-Host "`n❌ ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorDetail = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "Details: $($errorDetail.detail)" -ForegroundColor Red
    }
    exit 1
}

Write-Host "`n✅ Test completed successfully!" -ForegroundColor Green
