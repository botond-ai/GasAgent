# 📖 RÖVID BEVEZETŐ - Olvasd El Ezt Először!

**👋 Köszönöm, hogy értékeled ezt a projektet!**

Ez egy **teljes körűen működő LangGraph-alapú RAG Agent**, amely 9-node gráf-orchestration-nel működik, dokumentumokat indexel és AI-alapú kérdezésre ad válaszokat.

---

## ⚡ Gyors Start (5 perc)

### 1️⃣ Előfeltételek
```
✅ OpenAI API kulcs (https://platform.openai.com/api-keys)
✅ Python 3.9+ (ha lokálisan futtatod)
✅ Node.js 18+ (ha lokálisan futtatod)
✅ Docker + Docker Compose (javasolt - legegyszerűbb)
```

### 2️⃣ .env Konfigurálása
```bash
# Klóning után:
cp .env.example .env

# Szerkeszd a .env fájlt:
nano .env

# Add meg az OpenAI API kulcsod:
OPENAI_API_KEY=sk-... (ide jön a te kulcsod)
```

### 3️⃣ Szerver Indítása

#### **LEGEGYSZERŰBB: Docker Compose** ✅
```bash
docker-compose up --build

# Vár 30-40 másodpercet amíg felépül, majd:
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

#### **ALTERNATÍVA: Helyi Fejlesztés**
```bash
source .env && ./start-dev.sh

# Frontend: http://localhost:5173
# Backend: http://localhost:8000
```

---

## 🎯 Amit Fogsz Látni

### Frontend UI
```
1. Chat Paneel (bal oldal)
   - Kérdéseket küldhetsz
   - Válaszok dokumentum-alapúak

2. Dokumentum Feltöltés (jobb oldal)
   - Kategóriák létrehozása
   - Fájlok feltöltése

3. Activity Logger (jobb felső sarok: 📋)
   - Valós időben mutatja a feldolgozást
   - Processing → Success → Complete
```

### Demo Munkafolyamat
```bash
1. Nyisd meg: http://localhost:3000
2. Kattints a 📋 gombra (Activity Logger)
3. Töltsd fel a demo dokumentumokat:
   - DEMO_files_for_testing/HR_demo_hu.md → HR kategóriához
   - DEMO_files_for_testing/AI_vector_demo_hu.md → AI kategóriához
4. Kérdezz:
   - TESZT_QUESTIONS_FOR_THE_DEMO_FILES/AI_vector_demo_tesztkérdések.md
   - TESZT_QUESTIONS_FOR_THE_DEMO_FILES/HR_demo_tesztkérdések.md
   - pl. ezek vannak bennük:
   - "Mi a munkaszerződés?"
   - "Mi az embedding?"
   - "Ki az amerikai elnök?" (nem dokumentumokból)
5. Nézd meg a Sources panelt (válasz alatti Sources gomb)
```

---

## 🧪 Tesztelés

### Összes Teszt Futtatása
```bash
# A projekt 23 teljes körű tesztet tartalmaz
# 16 unit + 7 integration test
# Mindegyik már PASS-al fut ✅

pytest TESZTEK/test_workflow_basic.py TESZTEK/test_full_integration.py -v
```

### Teszt Státusza
```
✅ 23/23 teszt PASS (16 unit + 7 integration)
✅ 100% success rate
✅ Teljes körű funkcionalitás
✅ LangGraph workflow teljes lefedettség
```

---

## 📚 Dokumentáció

| Fájl | Mit Tartalmaz |
|------|--------------|
| **FULL_README.md** | Teljes projektleírás, API, architektúra |
| **LANGGRAPH_QUICKSTART.md** | LangGraph 5 perc intro (~200 sor) |
| **LANGGRAPH_IMPLEMENTATION.md** | Mélyrhatő 9-node architektúra (~400 sor) |
| **LANGGRAPH_INTEGRATION_GUIDE.md** | Integrációs lépések (~350 sor) |
| **FINAL_TEST_RESULTS.md** | Tesztelési eredmények (23/23 pass) |
| **TESZTEK/** | 2 db teszt file: test_workflow_basic.py + test_full_integration.py |

---

## 🔑 Főbb Funkciók

✅ **LangGraph Workflow (9 Node)**
- Validate → Category Routing → Embedding → Search → Dedup → Fallback → Generate → Format → End
- Explicit state tracking (20+ field)
- Activity callbacks minden csomópontnál

✅ **4 Dedikált API Node**
- LLM (kategória + válasz generálás)
- Embedding (szöveg vektorok)
- Search (vektor-hasonlóság)
- Fallback (intelligens tartalék keresés)

✅ **RAG Pipeline**
- Dokumentum-alapú válaszok
- Strukturált citations (metadata-val)
- Intelligens fallback mechanizmus

✅ **API Válasz Format (Modern)**
- rag_debug, api_info, debug_steps
- fallback_search info
- memory_snapshot

✅ **Chat Interfész**
- Kategória-alapú feltöltés
- Sources panel
- Reset context funkció

---

## ⚠️ Hibakeresés

### "Connection refused" hiba
```bash
# Ellenőrizd, hogy a szerver fut-e
ps aux | grep docker
# vagy
ps aux | grep start-dev.sh

# Ha nem fut, indítsd újra
docker-compose up --build
```

### "OpenAI API key error"
```bash
# Ellenőrizd a .env fájlt
cat .env

# Ha nincs OPENAI_API_KEY, add meg:
export OPENAI_API_KEY="sk-..."
```

### Activity Logger nem frissül
```bash
# Ellenőrizd az API végpontot
curl http://localhost:8000/api/health
# Válasz: {"status":"ok"}
```

---

## 📁 Mappastruktúra

```
gabor.toth/
├── README.md (FULL_README.md)  # Teljes dokumentáció ← OLVASD EL
├── QUICKSTART.md               # Demo útmutató ← HASZNÁLD
├── TEST_RESULTS.md             # Teszt eredmények
├── HW_SUMMARY.md               # Dolgozat összefoglalása
│
├── backend/               # Python FastAPI
│   ├── main.py
│   ├── requirements.txt
│   ├── domain/
│   ├── infrastructure/
│   └── services/
│
├── frontend/              # React + TypeScript
│   ├── src/
│   ├── package.json
│   └── Dockerfile
│
├── TESZTEK/
│   ├── test_workflow_basic.py      # 16 unit teszt
│   ├── test_full_integration.py    # 7 integration teszt
│   └── (23/23 PASS ✅)
├── DEMO_files_for_testing/  # HR + AI dokumentumok
│
├── docker-compose.yml     # Docker setup (ajánlott)
├── start-dev.sh          # Helyi szerver indítás
├── .env.example          # Environment sablon
└── .gitignore            # Git fájlok
```

---

## 🚀 Gyors Checklist

```
☐ 1. Git clone
☐ 2. cd mini_projects/gabor.toth
☐ 3. cp .env.example .env
☐ 4. Szerkeszd a .env-et (OpenAI API kulcs)
☐ 5. docker-compose up --build
☐ 6. Nyisd meg: http://localhost:3000
☐ 7. Kattints 📋 (Activity Logger)
☐ 8. Töltsd fel: DEMO_files_for_testing/HR_demo_hu.md
☐ 9. Kérdezz: "Mi a munkaszerződés?"
☐ 10. Nézd meg a Sources panelt
☐ 11. (Opcionális) Tesztek futtatása: `pytest TESZTEK/ -v`
```

---

## 💡 Mi Fogad?

✅ **LangGraph Workflow** - 9-node gráf-orchestration
✅ **4 Dedikált API Node** - Strukturált, maintainable API hívások
✅ **23/23 Teszt** - 16 unit + 7 integration (100% pass)
✅ **Teljes működő alkalmazás** - UI, backend, API
✅ **Professzionális dokumentáció** - 2550+ sor, 10 diagram
✅ **Modern API Format** - rag_debug, api_info, debug_steps
✅ **Docker Ready** - Azonnal futtatható
✅ **Bemutató Ready** - Demo dokumentumok + tesztkérdések

---

## ⏱️ Mennyi Ideig Tart?

```
⏱️ Szerver indítása (Docker): 30-40 másodperc
⏱️ Dokumentum feltöltése: 3-5 másodperc/doc
⏱️ Kérdés feldolgozása: 2-3 másodperc
⏱️ Tesztek futtatása: ~2-3 perc (összes 23)
```

---

## 🎓 Jó Tudni

**Mit NEM kell telepíteni:**
- `data/` mappa (auto-created)
- `node_modules/` (npm install által)
- Python venv (auto-created)

**Mit KELL telepíteni:**
- OpenAI API kulcs (SZÜKSÉGES!)
- Docker vagy Python+Node.js

**Mit LEHET tenni:**
- Docker Compose (legegyszerűbb)
- Helyi Python + Node.js (developer mode)

---

## 📞 Támogatás

**Kérdésed van?** Nézd meg:
1. **AT_A_GLANCE.md** - Rövid overview (ha nincs idő)
2. **LANGGRAPH_QUICKSTART.md** - 5 perc intro
3. **LANGGRAPH_IMPLEMENTATION.md** - Mélyrhatő leírás
4. **FULL_README.md** - Teljes dokumentáció
5. **FINAL_TEST_RESULTS.md** - Tesztelési info

---

## ✨ Összefoglalva

Ez egy **production-ready LangGraph RAG Agent**, amely:
- ✅ 9-node gráf orchestration (explicit, maintainable)
- ✅ 4 dedikált API node (strukturált API hívások)
- ✅ 23/23 teszt (16 unit + 7 integration, 100% pass)
- ✅ Professzionálisan dokumentálva (2550+ sor)
- ✅ Modern API formátum (rag_debug, api_info, debug_steps)
- ✅ Docker-ready
- ✅ Demo-ready

**Csak annyi kell:** OpenAI API kulcs + `docker-compose up`

**Ezután:** Dokumentumok feltöltése → Kérdezés → Válaszok dokumentum-alapúak!

---

**Jó tesztelést! 🚀**

---

*Utolsó frissítés: 2026. január 21.*
*Projekt státusza: ✅ Production Ready + LangGraph Integrated*
