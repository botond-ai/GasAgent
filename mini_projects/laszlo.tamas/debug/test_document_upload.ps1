# Test Document Upload Endpoint

Write-Host "=== TESTING DOCUMENT UPLOAD ENDPOINT ===" -ForegroundColor Cyan

# Create test files
$testDir = "test_files"
if (!(Test-Path $testDir)) {
    New-Item -ItemType Directory -Path $testDir | Out-Null
}

# Test 1: Create a simple TXT file
$txtContent = @"
This is a test document for the RAG system.

It contains multiple paragraphs to test the document upload functionality.

The document will be chunked and embedded for retrieval.
"@

$txtPath = "$testDir/test_doc.txt"
$txtContent | Out-File -FilePath $txtPath -Encoding UTF8
Write-Host "`n✅ Created test TXT file: $txtPath" -ForegroundColor Green

# Test 2: Create a Markdown file
$mdContent = @"
# Test Document

This is a **markdown** test document.

## Section 1

Some content in section 1.

## Section 2

Some content in section 2.
"@

$mdPath = "$testDir/test_doc.md"
$mdContent | Out-File -FilePath $mdPath -Encoding UTF8
Write-Host "✅ Created test MD file: $mdPath" -ForegroundColor Green

# Test 3: Upload TXT file
Write-Host "`n--- Test 1: Upload TXT file ---" -ForegroundColor Yellow

$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = (
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"test_doc.txt`"",
    "Content-Type: text/plain$LF",
    $txtContent,
    "--$boundary",
    "Content-Disposition: form-data; name=`"tenant_id`"$LF",
    "1",
    "--$boundary",
    "Content-Disposition: form-data; name=`"user_id`"$LF",
    "1",
    "--$boundary",
    "Content-Disposition: form-data; name=`"visibility`"$LF",
    "tenant",
    "--$boundary--$LF"
) -join $LF

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/documents/upload" `
        -Method POST `
        -ContentType "multipart/form-data; boundary=$boundary" `
        -Body $bodyLines

    Write-Host "✅ Upload successful!" -ForegroundColor Green
    Write-Host "Response: $($response.Content)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Upload failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Upload MD file
Write-Host "`n--- Test 2: Upload MD file ---" -ForegroundColor Yellow

$boundary2 = [System.Guid]::NewGuid().ToString()

$bodyLines2 = (
    "--$boundary2",
    "Content-Disposition: form-data; name=`"file`"; filename=`"test_doc.md`"",
    "Content-Type: text/markdown$LF",
    $mdContent,
    "--$boundary2",
    "Content-Disposition: form-data; name=`"tenant_id`"$LF",
    "1",
    "--$boundary2",
    "Content-Disposition: form-data; name=`"user_id`"$LF",
    "2",
    "--$boundary2",
    "Content-Disposition: form-data; name=`"visibility`"$LF",
    "private",
    "--$boundary2--$LF"
) -join $LF

try {
    $response2 = Invoke-WebRequest -Uri "http://localhost:8000/api/documents/upload" `
        -Method POST `
        -ContentType "multipart/form-data; boundary=$boundary2" `
        -Body $bodyLines2

    Write-Host "✅ Upload successful!" -ForegroundColor Green
    Write-Host "Response: $($response2.Content)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Upload failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== TEST COMPLETE ===" -ForegroundColor Cyan
