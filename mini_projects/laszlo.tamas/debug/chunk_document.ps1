# Chunk document by ID
param(
    [Parameter(Mandatory=$true)]
    [int]$DocumentId
)

# UTF-8 encoding for console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
chcp 65001 > $null

# Load backend port from .env
$envContent = Get-Content .env -ErrorAction SilentlyContinue
$BACKEND_PORT = ($envContent | Select-String "BACKEND_EXTERNAL_PORT=(\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) ?? "18000"

$url = "http://localhost:$BACKEND_PORT/api/documents/$DocumentId/chunk"

Write-Host "Chunking document ID: $DocumentId" -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json"
    
    Write-Host "`n✅ Document chunked successfully!" -ForegroundColor Green
    Write-Host "Document ID: $($response.document_id)" -ForegroundColor White
    Write-Host "Chunk Count: $($response.chunk_count)" -ForegroundColor White
    Write-Host "Chunk IDs: $($response.chunk_ids -join ', ')" -ForegroundColor White
}
catch {
    Write-Host "`n❌ Error chunking document:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    if ($_.ErrorDetails) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Yellow
    }
}
