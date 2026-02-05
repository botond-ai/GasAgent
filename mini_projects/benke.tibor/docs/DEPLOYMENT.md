# 🚀 Deployment Útmutató - KnowledgeRouter

> **Render.com Free Tier** - 100% ingyenes deployment CI/CD pipeline-nal
> 
> Tutorial technikák: GitHub Actions CI/CD, Multi-service orchestration, Health checks, Auto-rollback

---

## 📋 Tartalomjegyzék

1. [Platform Összehasonlítás](#platform-összehasonlítás)
2. [Render.com Deployment](#rendercom-deployment)
3. [Gyors Start Guide](#gyors-start-guide)
4. [Troubleshooting](#troubleshooting)

---

## Platform Összehasonlítás

| Platform | Free Tier | Előnyök | Hátrányok | Ajánlott? |
|----------|-----------|---------|-----------|-----------|
| **Render.com** | Unlimited (sleep after 15min) | PostgreSQL ingyen, Auto-deploy, Blueprint support | Cold start (30-60s), PostgreSQL 90 nap lejárat | ✅ **IGEN** |
| **Fly.io** | 3 VM ingyen | PostgreSQL, Redis ingyen, Gyors deployment | Komplex CLI, Nincs web UI | ❌ Túl bonyolult |
| **Heroku** | ❌ Nincs free tier | N/A | 2022 óta fizetős | ❌ NEM |

### 🏆 Ajánlás: **Render.com**

**Miért?**
- ✅ Teljesen ingyenes (korlátlan ideig)
- ✅ PostgreSQL managed database (90 nap, újraindítható)
- ✅ Web UI (egyszerű setup)
- ✅ GitHub auto-deploy (push → deploy)
- ✅ Blueprint support (render.yaml)

**Trade-off:**
- ❌ Sleep after 15 min inactivity (cold start: 30-60s)
- ❌ PostgreSQL 90 nap után expire (újra kell indítani)

---

## Render.com Deployment

### 1️⃣ Előkészületek

#### A) Render.com Account

1. Navigálj: [https://render.com/](https://render.com/)
2. **Sign up with GitHub** (GitHub OAuth)
3. Authorize Render app

#### B) Repository Setup

Ellenőrizd, hogy a következő fájlok megvannak:
- ✅ `render.yaml` (Blueprint config)
- ✅ `Dockerfile.redis` (Redis service)
- ✅ `Dockerfile.qdrant` (Qdrant vector DB)
- ✅ `backend/Dockerfile` (Django backend)
- ✅ `.github/workflows/deploy-render.yml` (CI/CD)

---

### 2️⃣ Blueprint Deployment

#### Lépések a Render Dashboard-on:

1. **New → Blueprint**
2. **Connect GitHub repository:**
   - Repository: `ai-agents-hu` (vagy a saját fork-od)
   - Branch: `main`
3. **Blueprint File:** `mini_projects/benke.tibor/render.yaml` (auto-detect)
4. **Review Services:**
   ```
   ✓ knowledgerouter-backend (Web Service)
   ✓ knowledgerouter-frontend (Static Site)
   ✓ knowledgerouter-db (PostgreSQL)
   ✓ knowledgerouter-redis (Private Service)
   ✓ knowledgerouter-qdrant (Private Service)
   ```
5. **Environment Variables Setup:**

   **Backend service-nél állítsd be:**
   ```bash
   # CRITICAL: OpenAI API Key
   OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
   
   # Optional: External APIs
   CONFLUENCE_BASE_URL=https://your-domain.atlassian.net
   CONFLUENCE_API_TOKEN=ATATT3xFfG...
   CONFLUENCE_EMAIL=user@example.com
   
   JIRA_BASE_URL=https://your-domain.atlassian.net
   JIRA_API_TOKEN=ATATT3xFfG...
   JIRA_EMAIL=user@example.com
   
   # Auto-generated (Render beállítja):
   # - SECRET_KEY (auto)
   # - POSTGRES_HOST/PORT/DB/USER/PASSWORD (auto-linked)
   # - REDIS_HOST/PORT (auto-linked)
   # - QDRANT_HOST/PORT (auto-linked)
   ```

6. **Deploy!** (5-10 perc)

---

### 3️⃣ GitHub Actions CI/CD Setup

#### A) GitHub Secrets beállítása

Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Szükséges secrets:

| Secret Name | Érték | Honnan szerezd? |
|-------------|-------|-----------------|
| `RENDER_DEPLOY_HOOK` | `https://api.render.com/deploy/srv-xxxxx?key=xxxxx` | Render Dashboard → Service → Settings → Deploy Hook |
| `RENDER_BACKEND_URL` | `https://knowledgerouter-backend.onrender.com` | Render Dashboard → Service URL |
| `SLACK_WEBHOOK_URL` (optional) | `https://hooks.slack.com/services/xxx` | Slack App → Incoming Webhooks |

#### B) Deploy Hook megszerzése (RENDER_DEPLOY_HOOK)

1. Render Dashboard → **knowledgerouter-backend** service
2. **Settings** tab
3. Scroll down → **Deploy Hook**
4. **Copy** → Paste GitHub Secrets-be

#### C) Tesztelés

```bash
# Push to main branch
git add .
git commit -m "feat: test Render deployment"
git push origin main
```

GitHub Actions workflow:
1. ✅ Test & Lint
2. ✅ Security Scan (Trivy)
3. ✅ Trigger Render Deploy
4. ✅ Health Check (`/api/healthz`)
5. ✅ API Test (sample query)

---

### 4️⃣ Első Deployment Ellenőrzése

#### A) Render Logs

1. Dashboard → **knowledgerouter-backend**
2. **Logs** tab
3. Ellenőrizd:
   ```
   ✓ Build successful
   ✓ Starting service...
   ✓ Uvicorn running on http://0.0.0.0:10000
   ✓ Health check passed
   ```

#### B) Manual Health Check

```bash
# Backend health
curl https://knowledgerouter-backend.onrender.com/api/healthz

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "qdrant": "connected"
}
```

#### C) Frontend Elérése

Navigálj: `https://knowledgerouter-frontend.onrender.com`

---

### 5️⃣ Cold Start Kezelése

**Probléma:** Sleep after 15 min → első request: 30-60s

**Megoldások:**

#### A) UptimeRobot Ping (Keep-Alive)

1. [https://uptimerobot.com/](https://uptimerobot.com/) (ingyenes)
2. **Add New Monitor**
   - Type: HTTP(S)
   - URL: `https://knowledgerouter-backend.onrender.com/api/healthz`
   - Interval: 5 minutes (Render free tier: 15 min sleep threshold)
3. **Create Monitor**

Result: Backend mindig "ébren" marad (4 ping/óra)

#### B) Beadandó Demo Előtt: Pre-Warm

```bash
# 5 perccel demo előtt (cold start elkerülése)
curl https://knowledgerouter-backend.onrender.com/api/healthz

# Várj 30s (backend felébredt)
# Most már fast response!
```

---

## Gyors Start Guide

### 🚀 Leggyorsabb Út: Render.com (5 perc)

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/ai-agents-hu.git
cd ai-agents-hu/mini_projects/benke.tibor

# 2. Render.com-on:
#    - New Blueprint
#    - Connect GitHub repo
#    - Blueprint file: mini_projects/benke.tibor/render.yaml
#    - Set OPENAI_API_KEY

# 3. GitHub Secrets (optional CI/CD):
#    - RENDER_DEPLOY_HOOK
#    - RENDER_BACKEND_URL

# 4. Push to main
git add .
git commit -m "feat: deploy to Render"
git push origin main

# 5. Várj 5-10 percet
# 6. Nyisd meg: https://knowledgerouter-backend.onrender.com
```

---

## Troubleshooting

### ❌ Render: "Build failed"

**Hiba:**
```
Step 5/10 : RUN pip install -r requirements.txt
ERROR: Could not find a version that satisfies the requirement...
```

**Megoldás:**
```bash
# backend/requirements.txt - ellenőrizd verziók kompatibilitását
pip install --upgrade pip
pip freeze > requirements.txt  # Frissítsd a lock fájlt
```

---

### ❌ Render: "Health check failed"

**Hiba:**
```
Health check timeout (30s)
```

**Megoldás:**

1. Ellenőrizd a health check endpoint:
   ```python
   # backend/api/views.py
   @api_view(['GET'])
   def healthz(request):
       return Response({"status": "healthy"})
   ```

2. Ellenőrizd a logokat:
   - Render Dashboard → Service → Logs
   - Keress: `ERROR`, `CRITICAL`

3. Növeld a timeout-ot (`render.yaml`):
   ```yaml
   healthCheckPath: /api/healthz
   # Render free tier: fix 30s timeout
   ```

---

### ❌ GitHub Actions: "Health check failed"

**Hiba:**
```
❌ Health check failed after 10 attempts (2.5 minutes)
```

**Megoldás:**

1. **Cold start:** Render sleep → várj 60s helyett 90s
   ```yaml
   # .github/workflows/deploy-render.yml
   - name: Wait for deployment (60 seconds)
     run: sleep 90  # 60 helyett 90
   ```

2. **Wrong URL:** Ellenőrizd GitHub Secret
   ```bash
   # GitHub Secrets: RENDER_BACKEND_URL
   # Helyes: https://knowledgerouter-backend.onrender.com
   # Helytelen: http://knowledgerouter-backend.onrender.com (http!)
   ```

3. **CORS hiba:** Django settings
   ```python
   # core/settings.py
   ALLOWED_HOSTS = ['.onrender.com', 'localhost', '127.0.0.1']
   ```

---

### ❌ PostgreSQL: "90 day expiration"

**Hiba:**
```
Free PostgreSQL databases expire after 90 days
```

**Megoldás:**

1. **Backup exportálása** (90. nap előtt):
   ```bash
   # Render Dashboard → Database → Backups → Download
   ```

2. **Új database létrehozása:**
   - Dashboard → New PostgreSQL
   - Restore backup:
     ```bash
     pg_restore -h new-db.render.com -U user -d dbname backup.dump
     ```

---

## Tutorial Technikák Összefoglalása

### ✅ Alkalmazott DevOps Best Practices

| Tutorial Technika | Implementáció | Fájl |
|-------------------|---------------|------|
| **GitHub Actions CI/CD** | Test → Build → Deploy → Health Check | `.github/workflows/deploy-render.yml` |
| **Multi-service Orchestration** | 5 konténer (backend, frontend, DB, cache, vector DB) | `render.yaml` |
| **Health Checks** | `/api/healthz` endpoint, retry logic | `deploy-render.yml` (lines 150-180) |
| **Environment Variables** | Secrets management (OPENAI_KEY), Database auto-link | `render.yaml` (envVars) |
| **Docker Multi-stage Build** | Layer caching, size optimization | `backend/Dockerfile` |
| **Security Scanning** | Trivy vulnerability scan | `deploy-render.yml` (job: security-scan) |
| **Auto-rollback** | Health check fail → previous version | Render auto-rollback |
| **Monitoring** | Logs aggregation (Render Logs) | Render Dashboard |

---

## Összefoglalás

### 🎯 Setup Ajánlás

1. **Platform:** Render.com (100% ingyenes)
2. **Services:** Backend + Frontend + PostgreSQL + Redis + Qdrant (5 service)
3. **Monitoring:** Render beépített metrics
4. **CI/CD:** GitHub Actions (auto-deploy main push-ra)
5. **Cold Start Fix:** UptimeRobot ping (5 perc interval)

### ⏱️ Setup Idő: ~15-20 perc

1. Render.com Blueprint setup: 5 perc
2. Environment variables: 3 perc
3. GitHub Secrets: 2 perc
4. First deployment: 5-10 perc
5. Health check + test: 2 perc

### 💰 Költség: $0/hó (100% ingyenes)

### 📚 Tanult Technikák

- ✅ Infrastructure as Code (render.yaml Blueprint)
- ✅ CI/CD automation (GitHub Actions)
- ✅ Multi-service deployment (5 container orchestration)
- ✅ Health monitoring (automated health checks)
- ✅ Security scanning (Trivy vulnerability detection)
- ✅ Environment management (secrets, configs)
- ✅ Auto-scaling (Render auto-scale on load)

---

**Következő lépés:** Regisztrálj a Render.com-ra és kövesd a [Gyors Start Guide](#gyors-start-guide)-ot! 🚀
