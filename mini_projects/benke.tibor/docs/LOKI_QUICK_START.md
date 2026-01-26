# Loki Quick Start Guide - Első Lépések

## 🚀 Kipróbálás 5 percben

### 1️⃣ Stack indítása

```bash
# Terminal
cd c:\Python_codes\ai-agents-hu\mini_projects\benke.tibor

# Indítsd a teljes stack-et (vagy csak Loki komponenseket)
docker-compose up -d loki promtail grafana

# Vagy teljes stack:
docker-compose up -d
```

**Mit indít ez el:**
- Loki: `localhost:3100` - Log aggregation API
- Promtail: `localhost:9080` - Log shipper
- Grafana: `localhost:3001` - Visualization UI

### 2️⃣ Ellenőrzés (3100-as port)

```bash
# Loki health check
curl http://localhost:3100/ready
# Válasz: ready

# Loki metrics
curl http://localhost:3100/metrics
# Válasz: Prometheus formátumú metrikák

# Loki API verzió
curl http://localhost:3100/loki/api/v1/labels
# Válasz: {"status":"success","data":["job","service",...]}
```

**Mit látsz a 3100-on:**
- `/ready` - egyszerű "ready" szöveg (HTTP 200 ha fut)
- `/metrics` - Prometheus metrikák (nem emberi olvasásra)
- `/loki/api/v1/*` - JSON API (LogQL queries futtatásához)

**⚠️ FONTOS:** A 3100-as port **nem böngészőből használható UI**, csak API! A vizualizációhoz Grafanát kell használni (3001-es port).

### 3️⃣ Grafana UI (ez kell neked!)

```
URL: http://localhost:3001
Username: admin
Password: admin
```

**Mit látsz:**
1. **Login screen** → bejelentkezés (admin/admin)
2. **Welcome screen** → bal oldali menü
3. **Explore** (kompasz ikon) → ide kattints!
4. **Datasource selector** (fent) → válaszd: "Loki"
5. **Query editor** → írj be: `{job="backend"}`
6. **Run query** (jobb oldal, "Run query" gomb)

**Mit fogsz látni most (még ÜRES lesz!):**
- "No data" vagy "No logs found"
- **Miért?** Mert a backend még nem használja a structured logging-ot!

---

## 4️⃣ Backend Integráció (EZEK KELLENEK!)

Most jön az integráció - **3 fájlt kell módosítani:**

### A) `core/settings.py` - Logging setup at startup

```python
# core/settings.py - Add at the END of file

# ============================================================================
# STRUCTURED LOGGING SETUP (Loki Integration)
# ============================================================================
import os
from infrastructure.structured_logging import setup_structured_logging

# Initialize structured logging at app startup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
JSON_LOGGING = os.getenv("JSON_LOGGING", "true").lower() == "true"

setup_structured_logging(
    log_level=LOG_LEVEL,
    log_file=None,  # None = stdout only (Docker logs), or "/var/log/backend/app.log"
    json_format=JSON_LOGGING  # True in production (for Loki), False in dev (readable)
)

print(f"✅ Structured logging configured: level={LOG_LEVEL}, json={JSON_LOGGING}")
```

### B) `services/agent.py` - Use structured logging in nodes

**BEFORE (jelenlegi kód):**
```python
logger.info("Intent detection node executing")
logger.info(f"Detected domain: {domain}")
```

**AFTER (structured logging):**
```python
from infrastructure.structured_logging import log_node_execution

# Intent detection node
log_node_execution(
    logger,
    node="intent_detection",
    message="Intent detection completed",
    level="INFO",
    domain=domain,
    user_id=state.get("user_id", "unknown"),
    session_id=state.get("session_id", "unknown")
)

# Generation node with latency
import time
start_time = time.time()
# ... LLM call ...
latency_ms = (time.time() - start_time) * 1000

log_node_execution(
    logger,
    node="generation",
    message="LLM response generated",
    level="INFO",
    domain=domain,
    user_id=state.get("user_id"),
    session_id=state.get("session_id"),
    latency_ms=latency_ms,
    tokens=total_tokens,  # ha van
    cost=cost_usd  # ha van
)
```

### C) `.env` - Enable JSON logging

```bash
# .env
LOG_LEVEL=INFO
JSON_LOGGING=true  # FONTOS: true a Loki-hoz!
```

---

## 5️⃣ Újraindítás és Teszt

```bash
# 1. Állítsd le a backend-et
docker-compose stop backend

# 2. Újraindítás (betölti az új settings.py-t)
docker-compose up -d backend

# 3. Nézd meg a log-okat (most már JSON formátumban!)
docker-compose logs backend --tail 20

# Példa JSON output:
# {"timestamp":"2026-01-23T10:30:45.123456Z","level":"INFO","name":"services.agent",
#  "message":"Intent detection completed","node":"intent_detection","domain":"it",
#  "user_id":"user123","session_id":"session456"}
```

**Ha látod a JSON-t a `docker-compose logs` outputban → MŰKÖDIK!** ✅

---

## 6️⃣ Logok megtekintése Grafanában

### Most már látnod KELL adatokat!

1. **Grafana:** http://localhost:3001
2. **Explore** → Loki datasource
3. **Query:**
   ```logql
   {job="backend"}
   ```
4. **Time range:** "Last 15 minutes" (fent jobb oldal)
5. **Run query**

**Mit látsz most:**
- ✅ JSON log sorok időbélyeggel
- ✅ Filters: level, node, domain (bal oldali "Labels" panel)
- ✅ Log details: kattints egy sorra → JSON fields kibontva

### Példa Queries (próbáld ki):

```logql
# Csak ERROR szintű logok
{job="backend"} | json | level="ERROR"

# Intent detection node logjai
{job="backend"} | json | node="intent_detection"

# IT domain logok
{job="backend"} | json | domain="it"

# Lassú query-k (>5 sec)
{job="backend"} | json | latency_ms > 5000

# Konkrét user összes loga
{job="backend"} | json | user_id="user123"
```

---

## 7️⃣ Dashboard készítés (opcionális, de hasznos!)

### Quick Dashboard 3 panellel:

1. **Grafana** → Dashboards → New Dashboard
2. **Add visualization** → típus: "Time series" vagy "Logs"
3. **Panel 1: Error Rate**
   - Query: `sum(rate({job="backend"} | json | level="ERROR" [1m]))`
   - Visualizáció: Graph

4. **Panel 2: Latency by Node**
   - Query: `avg_over_time({job="backend"} | json | latency_ms [5m]) by (node)`
   - Visualizáció: Graph (multi-line)

5. **Panel 3: Recent Logs**
   - Query: `{job="backend"}`
   - Visualizáció: Logs

6. **Save dashboard** (fent jobb oldal)

---

## 🎯 Összefoglaló - Mit kell csinálni:

### ✅ Checklist:

- [x] **1. docker-compose up -d** (már futtatod)
- [x] **2. curl http://localhost:3100/ready** (ellenőrzés)
- [ ] **3. Módosítsd `core/settings.py`** (structured logging setup)
- [ ] **4. Módosítsd `services/agent.py`** (használd `log_node_execution()`)
- [ ] **5. Módosítsd `.env`** (add hozzá `LOG_LEVEL=INFO` és `JSON_LOGGING=true`)
- [ ] **6. docker-compose restart backend** (újraindítás)
- [ ] **7. docker-compose logs backend --tail 20** (JSON logok látszódjanak)
- [ ] **8. Grafana → Explore → Loki → {job="backend"}** (első query)
- [ ] **9. Készíts dashboard-ot** (opcionális, de ajánlott)

### 🎨 Gyors win (teszteléshez):

**Egyetlen sor hozzáadása `core/settings.py` végére:**

```python
# core/settings.py - at the very end
from infrastructure.structured_logging import setup_structured_logging
setup_structured_logging(log_level="INFO", json_format=True)
print("✅ Loki logging enabled")
```

**Újraindítás:**
```bash
docker-compose restart backend
docker-compose logs backend --tail 5
```

**Ha látod a JSON-t → KÉSZ! Menj Grafanába és query-zd: `{job="backend"}`**

---

## 🐛 Troubleshooting

### "No data" Grafanában

**Okok:**
1. Backend még nem JSON-t loggol → `docker-compose logs backend` (nézd meg a formátumot)
2. Promtail nem scrape-el → `curl http://localhost:9080/metrics | grep promtail_targets_active_total`
3. Time range rossz → Grafanában állítsd "Last 15 minutes"-re

### Backend nem indul újra

```bash
# Nézd meg a hibát
docker-compose logs backend --tail 50

# Ha import error van:
# - ellenőrizd, hogy infrastructure/structured_logging.py létezik-e
# - docker-compose build backend (újraépítés)
```

### JSON log nem jelenik meg

```bash
# Ellenőrzés:
docker-compose exec backend python -c "
from infrastructure.structured_logging import setup_structured_logging
import logging
setup_structured_logging(log_level='INFO', json_format=True)
logger = logging.getLogger(__name__)
logger.info('Test message', extra={'node': 'test', 'domain': 'it'})
"
# Ha JSON-t látsz → működik
# Ha exception → import hiba vagy syntax error
```

---

**Kérdésed van bármelyik lépésnél? Vagy elakadtál valahol?**
