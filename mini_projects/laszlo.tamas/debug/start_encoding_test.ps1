# Complete Encoding Debug Test
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ENCODING DEBUG PANEL - TELJES TESZT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$API_BASE = "http://localhost:8000/api"

# Step 1: Reset databases
Write-Host "[1/2] Database reset..." -ForegroundColor Yellow
try {
    $pgResult = Invoke-RestMethod -Uri "$API_BASE/debug/reset/postgres" -Method POST
    Write-Host "  PostgreSQL: $($pgResult.documents_deleted) docs, $($pgResult.chunks_deleted) chunks torolve" -ForegroundColor Green
    
    $qdResult = Invoke-RestMethod -Uri "$API_BASE/debug/reset/qdrant" -Method POST
    Write-Host "  Qdrant: $($qdResult.status) - $($qdResult.message)" -ForegroundColor Green
} catch {
    Write-Host "  HIBA: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/2] Frontend status..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
        Write-Host "  Frontend: OK (http://localhost:3000)" -ForegroundColor Green
    }
} catch {
    Write-Host "  Frontend: Nem elerheto" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "            TESZT UTASITASOK" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Nyisd meg: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "2. Valassz TENANT es USER-t a dropdown-okbol" -ForegroundColor White
Write-Host ""
Write-Host "3. Gorgess le az 'Encoding Debug Panel'-hez" -ForegroundColor White
Write-Host ""
Write-Host "4. Most mar RESET nelkul is folytathatod:" -ForegroundColor Yellow
Write-Host "   (az adatbazisok mar uresek)" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Valassz egy MAGYAR UTF-8 fajlt:" -ForegroundColor White
Write-Host "   - test_files/fantasy_large.txt" -ForegroundColor Gray
Write-Host "   - Vagy barmilyen mas .txt/.md fajl" -ForegroundColor Gray
Write-Host ""
Write-Host "6. Kattints UPLOAD gombra" -ForegroundColor White
Write-Host "   -> Ellenorizd a PREVIEW-t (elso 200 karakter)" -ForegroundColor Yellow
Write-Host "   -> Helyesek az ekezetes betuk? (a, e, i, o, u)" -ForegroundColor Yellow
Write-Host ""
Write-Host "7. Kattints CHUNK gombra" -ForegroundColor White
Write-Host "   -> Ellenorizd a CHUNKS PREVIEW-t" -ForegroundColor Yellow
Write-Host ""
Write-Host "8. Kattints READ FROM POSTGRESQL gombra" -ForegroundColor White
Write-Host "   -> Ellenorizd a POSTGRESQL PREVIEW-t" -ForegroundColor Yellow
Write-Host ""
Write-Host "9. Kattints EMBED TO QDRANT gombra" -ForegroundColor White
Write-Host "   -> Sikeres! Zold 'Process Complete!' uzenet" -ForegroundColor Yellow
Write-Host ""
Write-Host "10. Most teszteld a RAG CHAT-et:" -ForegroundColor White
Write-Host "    - Gorgess le a chat ablakhoz" -ForegroundColor Gray
Write-Host "    - Kerj ra a dokumentumra (pl. 'Ki az a Aria?')" -ForegroundColor Gray
Write-Host "    - Nezd meg hogy a valaszban helyesek-e az ekezetek" -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "BACKEND SWAGGER UI: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Ha problemaval talalkozsz:" -ForegroundColor Yellow
Write-Host "  docker logs ai_chat_phase2-backend-1 --tail 50" -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "         KESZEN VAGY A TESZTHEZ!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
