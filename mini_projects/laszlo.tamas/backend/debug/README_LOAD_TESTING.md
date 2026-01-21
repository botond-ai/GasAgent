# Load Testing with Locust

## 🎯 Gyors Start

### 1. Telepítés
```powershell
pip install locust
```

### 2. Backend Indítás (ha még nem fut)
```powershell
cd knowledge_router
docker-compose up -d
```

### 3. Load Test Futtatás

#### Opció A: PowerShell Script (ajánlott)
```powershell
# Alapértelmezett (5 user, 60 sec)
.\backend\debug\run_load_test.ps1

# Custom konfiguráció
.\backend\debug\run_load_test.ps1 -Users 10 -Duration 120

# Headless mód (CLI only, HTML report)
.\backend\debug\run_load_test.ps1 -Users 5 -Headless
```

#### Opció B: Manuális Locust
```powershell
# Web UI mód (interaktív)
locust -f backend/debug/load_test_chat.py --host=http://localhost:8000

# Headless mód
locust -f backend/debug/load_test_chat.py --host=http://localhost:8000 --headless --users 5 --spawn-rate 1 --run-time 60s
```

---

## 📊 Web Dashboard Használat

1. **Indítás után:** http://localhost:8089
2. **Number of users:** `5` (kezdj kicsivel!)
3. **Spawn rate:** `1` (user/sec)
4. **Host:** `http://localhost:8000` (már be van állítva)
5. **Start swarming**

### Dashboard Metrikák
- **RPS (Requests Per Second):** Aktuális terhelés
- **Response Time (ms):** Átlagos/P95/P99 válaszidő
- **Failures:** Sikertelen kérések aránya
- **Charts:** Valós idejű grafikonok

---

## ⚙️ Task Distribution

| Task | Súly | Leírás |
|------|------|--------|
| `simple_chat_question` | 60% | Egyszerű kérdés (nincs dokumentum keresés) |
| `document_search_question` | 30% | Dokumentum-alapú kérdés (Qdrant query) |
| `health_check` | 10% | Health endpoint (minimális terhelés) |

**User behavior:**
- 2-5 sec várakozás kérések között (természetes)
- Random `user_id` 1-10 között
- Mindegyik user `tenant_id=1`

---

## 🔥 Terhelési Ajánlások

### Biztonságos Profil (1 worker setup)
```
Users: 5-10
Spawn Rate: 1 user/sec
Duration: 60-120 sec
Expected RPS: 1-5
```

### Közepes Terhelés
```
Users: 10-20
Spawn Rate: 2 user/sec
Duration: 120-300 sec
Expected RPS: 5-10
```

### Agresszív Teszt (csak ha van több worker!)
```
Users: 50+
Spawn Rate: 5 user/sec
Duration: 300+ sec
Expected RPS: 20+
```

**⚠️ FIGYELEM:** LLM hívások miatt 1 request = 2-5 sec, így 10 concurrent user már ~2-5 RPS terhelés!

---

## 📈 Lépcsős Terhelés (Step Load)

A `load_test_chat.py` tartalmaz egy `StepLoadShape` osztályt:

```python
# Terhelési profil:
# 0-60s:   5 user
# 60-120s: 10 user
# 120-180s: 15 user
# 180-240s: 20 user
```

**Használat:**
```powershell
locust -f backend/debug/load_test_chat.py --host=http://localhost:8000 --headless --users 20 --spawn-rate 1
```

Ez automatikusan követi a lépcsős terhelést.

---

## 🐛 Troubleshooting

### Backend nem válaszol
```powershell
# Ellenőrizd a backend logokat
docker logs knowledge_router_backend --tail 50

# Restart backend
docker-compose restart backend
```

### Locust hiba: "Connection refused"
- Backend nem fut vagy nem érhető el
- Ellenőrizd: http://localhost:8000/docs

### Túl sok timeout (request > 30s)
- LLM hívások lassúak
- Csökkentsd a concurrent user számot
- Ellenőrizd az OpenAI API rate limiteket

### Qdrant connection errors
```powershell
# Ellenőrizd Qdrant health
docker logs knowledge_router_qdrant --tail 20
```

---

## 📊 Output Files

### HTML Report (headless mode)
```
backend/debug/load_test_report.html
```

Tartalmazza:
- Request statistics (min/max/avg/P95/P99)
- Failure rate
- RPS trend
- Teljes teszt summary

### CSV Export (Web UI)
Locust Web UI → "Download Data" → CSV

---

## 🚀 Következő Lépések

### 1. Multi-Worker Setup
```dockerfile
# Dockerfile módosítás
CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### 2. Distributed Load Testing
```powershell
# Master node
locust -f backend/debug/load_test_chat.py --master --host=http://localhost:8000

# Worker nodes (több terminalban)
locust -f backend/debug/load_test_chat.py --worker --master-host=localhost
locust -f backend/debug/load_test_chat.py --worker --master-host=localhost
```

### 3. CI/CD Integration
```yaml
# GitHub Actions
- name: Load Test
  run: |
    locust -f backend/debug/load_test_chat.py --headless --users 10 --spawn-rate 2 --run-time 60s --host=http://localhost:8000
```

---

**Last Updated:** 2026-01-18
