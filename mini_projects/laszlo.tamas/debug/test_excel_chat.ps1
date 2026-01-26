# Test Excel via Chat API
$body = @{
    query = "Create an Excel file called sales_report.xlsx with a sheet named Sales and add data: Product-Price rows: Laptop-999, Phone-599, Tablet-399"
    user_context = @{
        tenant_id = 1
        user_id = 1
    }
} | ConvertTo-Json -Compress

Write-Host "Request: $body"
Write-Host ""

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/chat/" -Method POST -Body $body -ContentType "application/json; charset=utf-8"

Write-Host "Answer:"
Write-Host $response.answer
Write-Host ""
Write-Host "Actions taken:"
$response.actions_taken | ForEach-Object { Write-Host "  - $_" }
