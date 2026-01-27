# KnowledgeRouter (HF1–HF4) — Patch #2 (HF1+HF3 alap)

Patch #2 cél:
- **HF1**: publikus API tool (Open‑Meteo) + hibakezelés + teszt
- **HF3**: orchestration: triage routing (rag/api/mixed) + state-be integrált tool eredmények + mocked flow teszt
- **Demo**: minimál web UI (FastAPI + 1 HTML form) `docker compose up` után

## Kötelező Docker parancsok (stabil)

Megjegyzés: a projekt **dockerben futtatandó**. A `langgraph` + `faiss-cpu` függőségek a konténerben települnek; hoston futtatva külön `pip install -r requirements.txt` kell.

```bash
docker compose build
docker compose run --rm app python scripts/index_docs.py --input docs --out data/index
docker compose run --rm app python scripts/eval_rag.py
docker compose run --rm app python -m app.cli chat
docker compose run --rm app pytest -q
```

## Demo: web UI (látvány)

```bash
cp .env.example .env
docker compose up -d
```

Nyisd meg:
- http://localhost:8000

## HF1 demo (Open‑Meteo)

Chat-ben:
- `Milyen az időjárás Budapesten?`

Elvárt:
- nem nyers JSON, hanem rövid szöveg (temperature, wind)
- tool eredmény a `tool_results.open_meteo` alatt

## HF2 demo (RAG)

Index:
```bash
docker compose run --rm app python scripts/index_docs.py --input docs --out data/index
```

Chat:
- `Mi az IT policy VPN hibára?`
- `HR onboardingnál mik a kötelező lépések?`

Elvárt: válasz + citációk `docs/*` alapján.

## HF3 demo (Orchestration: RAG + Open‑Meteo)

Chat:
- `A dokumentum szerint mi a teendő VPN hibánál, és milyen az időjárás Budapesten?`

Elvárt:
- triage: `route=mixed`
- RAG válasz citációkkal
- Open‑Meteo summary hozzáfűzve
- mindkettő a state-ben (`tool_results`)

## Konfig

- `DEV_MODE=1` (default): determinisztikus, nincs hálózat (teszt / demo)
- `DEV_MODE=0`: éles OpenAI + éles Open‑Meteo (kell `OPENAI_API_KEY`)

Ticket API (későbbi workflowhoz / demóhoz):
- `TICKET_DRY_RUN=1`: a ticket payload fájlba mentődik `data/tickets/` alá
- `TICKET_DRY_RUN=0`: HTTP a `ticket-api` service felé
