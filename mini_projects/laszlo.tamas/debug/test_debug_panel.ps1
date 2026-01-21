# Encoding Debug Panel - Teljes Teszt
# Force UTF-8 output
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Encoding Debug Panel Test ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "A debug panel keszen all a kovetkezo cimen:" -ForegroundColor Green
Write-Host "  http://localhost:3000" -ForegroundColor White
Write-Host ""

Write-Host "A panel funkcioi:" -ForegroundColor Yellow
Write-Host "  1. Reset - Torli a PostgreSQL es Qdrant adatbazisokat" -ForegroundColor White
Write-Host "  2. Upload - Feltolt egy dokumentumot" -ForegroundColor White
Write-Host "  3. Preview - Mutatja az elso 200 karaktert (encoding ellenorzes)" -ForegroundColor White
Write-Host "  4. Chunk - Chunkolja a dokumentumot" -ForegroundColor White
Write-Host "  5. Chunks Preview - Mutatja a chunk-ok elso 200 karakteret" -ForegroundColor White
Write-Host "  6. PostgreSQL Verify - Visszaolvassa a chunk-ot a database-bol" -ForegroundColor White
Write-Host "  7. Embed - Letrehozza az embeddinget es beteszi Qdrantba" -ForegroundColor White
Write-Host ""

Write-Host "Teszteles lepései:" -ForegroundColor Cyan
Write-Host "  1. Nyisd meg: http://localhost:3000" -ForegroundColor White
Write-Host "  2. Valassz tenant-ot es user-t" -ForegroundColor White
Write-Host "  3. Gorgess le az 'Encoding Debug Panel'-hez" -ForegroundColor White
Write-Host "  4. Kattints a 'Reset PostgreSQL & Qdrant' gombra" -ForegroundColor White
Write-Host "  5. Valassz egy magyar UTF-8 dokumentumot (pl. fantasy dokumentum)" -ForegroundColor White
Write-Host "  6. Kattints vegig a lepeseken:" -ForegroundColor White
Write-Host "     - Upload -> Chunk -> Verify PostgreSQL -> Embed to Qdrant" -ForegroundColor Gray
Write-Host "  7. Minden lepesnel ellenorizd a preview szovegeket" -ForegroundColor White
Write-Host "  8. Nezd meg hogy az ekezetes betuk helyesen jelennek-e meg" -ForegroundColor White
Write-Host ""

Write-Host "Backend endpoint-ok (teszteleshez):" -ForegroundColor Yellow
Write-Host "  POST /api/debug/reset/postgres" -ForegroundColor Gray
Write-Host "  POST /api/debug/reset/qdrant" -ForegroundColor Gray
Write-Host "  GET  /api/debug/documents/{id}/preview" -ForegroundColor Gray
Write-Host "  GET  /api/debug/documents/{id}/chunks/preview" -ForegroundColor Gray
Write-Host ""

# Test backend endpoints
Write-Host "Backend endpoint teszt..." -ForegroundColor Cyan
try {
    Write-Host "  Swagger UI: http://localhost:8000/docs" -ForegroundColor White
    $health = Invoke-RestMethod -Uri "http://localhost:8000/docs" -UseBasicParsing -ErrorAction SilentlyContinue
    Write-Host "  OK Backend elerheto" -ForegroundColor Green
} catch {
    Write-Host "  ! Backend lehet hogy meg indul" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "A rendszer keszen all az encoding debuggolasra!" -ForegroundColor Green
