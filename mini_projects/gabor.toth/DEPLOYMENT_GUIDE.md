# 🚀 Deployment Guide - RAG Agent to Local VPS

> **⚠️ NOTE**: Ez a deployment workflow **manuális trigger** GitHub Actions-ből. Nem automatikus push-nál - ez a közös repo egyenlege miatt így lett beállítva.

---

## 📋 Előfeltételek

### VPS-en (szerv-oldal):

1. **OS**: Ubuntu 20.04+ vagy Debian 11+
2. **Szoftver**:
   - Git (`git --version`)
   - Docker (`docker --version`)
   - Docker Compose (`docker-compose --version`)
   - curl (health check-hez)

3. **Felhasználó**: 
   - SSH user (default: `ubuntu`)
   - Sudoer jogok (Docker futtatáshoz)

4. **Klón**: Repository már klónozva
   ```bash
   cd /home/ubuntu
   git clone https://github.com/Global-rd/ai-agents-hu.git
   cd ai-agents-hu/mini_projects/gabor.toth
   ```

5. **Environment fájl**:
   ```bash
   cp .env.example .env
   # Szerkeszd az .env-t és add meg az OPENAI_API_KEY-t
   nano .env
   ```

6. **Docker demon** futása:
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

---

## 🔑 GitHub Secrets Setup

A workflow-nak szüksége van 2 secretre a repo Secrets-ben. Ezeket a GitHub repo Settings → Secrets and variables → Actions menübe kell beírni:

| Secret Név | Érték | Példa |
|-----------|-------|-------|
| `DEPLOY_HOST` | VPS IP vagy hostname | `192.168.1.100` vagy `deploy.example.com` |
| `DEPLOY_USER` | SSH felhasználó | `ubuntu` |
| `DEPLOY_SSH_KEY` | **Privát** SSH kulcs | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

### Hogyan generálj SSH kulcsot?

**1. Lokálisan (fejlesztői gép):**
```bash
ssh-keygen -t ed25519 -C "github-actions-rag-agent" -f ~/.ssh/id_github_rag -N ""
```

**2. Public kulcs másolása VPS-re:**
```bash
ssh-copy-id -i ~/.ssh/id_github_rag.pub ubuntu@YOUR_VPS_IP
```

Vagy manuálisan:
```bash
# VPS-en:
mkdir -p ~/.ssh
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

**3. Privát kulcs GitHub-ba:**
- nyisd meg: `~/.ssh/id_github_rag`
- másolj ki **teljes tartalmat** (BEGIN-ből END-ig)
- illeszd be a GitHub Secrets `DEPLOY_SSH_KEY` értékeként

---

## 🚀 Deployment Indítása

### GitHub UI-ből (Ajánlott):

1. GitHub repo → **Actions** tab
2. Bal oldalon: **Deploy RAG Agent to Local Server**
3. **Run workflow** gomb
4. Válaszd az environment-et (production/staging)
5. Kattints a **Run workflow** zöld gombra
6. Nézd meg a live loggokat

### GitHub CLI-ből:

```bash
gh workflow run deploy-local-server.yml -f environment=production
```

### Manuálisan (Git push nélkül):

```bash
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/Global-rd/ai-agents-hu/actions/workflows/deploy-local-server.yml/dispatches \
  -d '{"ref":"main","inputs":{"environment":"production"}}'
```

---

## 📊 Workflow Mi Történik?

```
0. Code checkout (GitHub Actions kontextus)
   ↓
1. SSH key setup
   ├─ Privát kulcs dekódolása
   └─ VPS hostname hozzáadása known_hosts-hoz
   ↓
2. PRE-DEPLOYMENT HEALTH CHECK
   ├─ Van-e működő backend?
   └─ Van-e működő frontend?
   ↓
3. BACKUP PERSISTENT DATA
   ├─ data/users biztonsági mentése
   └─ data/sessions biztonsági mentése
      (Rollback-hoz, ha probléma van)
   ↓
4. GIT PULL
   ├─ git fetch origin
   ├─ git checkout main
   └─ git pull origin main
   ↓
5. GRACEFUL DOCKER UPDATE
   ├─ docker-compose pull (új image letöltése)
   └─ docker-compose up -d --build (graceful restart)
   ↓
6. HEALTH CHECK - BACKEND
   ├─ Loop: max 30x, 10mp között
   ├─ GET http://localhost:8000/api/health
   └─ ✅ vagy ❌ logs + exit
   ↓
7. HEALTH CHECK - FRONTEND
   ├─ Loop: max 15x, 5mp között
   ├─ GET http://localhost:3000 (status 200 vagy 301)
   └─ ⚠️ (warning, de nem kritikus, ha timeout)
   ↓
8. SMOKE TEST
   ├─ Backend API response validálása
   └─ "ok" field keresése a JSON-ben
   ↓
9. DETAILED LOGS & METRICS
   ├─ docker-compose ps (service státusz)
   ├─ Backend & frontend naplók (15 sor)
   └─ docker stats (CPU, memória használat)
   ↓
10. SUCCESS SUMMARY
    ├─ Backend & Frontend URL-ek
    ├─ Confirmation: "Application is now live!"
    └─ Összefoglalás (sikeres vagy sikertelen)
```

**Total time**: ~5-8 perc (ha mindent bem fut felül)

---

## 🐛 Troubleshooting

### ❌ "Pre-deployment health check says no service running"

**OK**: Első deployment vagy szerver le volt állítva

**Fix**: Ez nem hiba! A workflow így vagy úgy működik. A `docker-compose up -d --build` felépíti.

---

### ❌ "SSH Connection Failed"

**OK**: SSH kulcs vagy host nem jó

**Fix**:
```bash
# Ellenőrizd GitHub Secretsben:
# 1. DEPLOY_HOST = valid IP vagy hostname
# 2. DEPLOY_USER = ubuntu (vagy a te ssh user-ed)
# 3. DEPLOY_SSH_KEY = -----BEGIN OPENSSH PRIVATE KEY-----...

# VPS-en, ellenőrizd az authorized_keys:
cat ~/.ssh/authorized_keys | grep "github-actions"
```

---

### ❌ "Git pull failed - authentication"

**OK**: VPS-en nincs Git SSH key vagy credentials

**Fix - VPS-en**:
```bash
# GitHub SSH key setup (ha private repo)
ssh-keygen -t ed25519 -C "vps-deployment" -f ~/.ssh/id_github -N ""

# Public key hozzáadása GitHub-ban (Settings → SSH Keys)
cat ~/.ssh/id_github.pub

# Git config
git config --global user.name "Deployment"
git config --global user.email "deploy@example.com"
```

---

### ❌ "Docker Build Failed - disk space"

**OK**: Docker image túl nagy vagy nincs hely

**Fix**:
```bash
# VPS-en, lemez check
df -h

# Docker cleanup
docker system prune -a --volumes

# Szabad hely
docker system df
```

---

### ❌ "Backend health check failed - timeout"

**OK**: 5 perc alatt nem indult el a backend

**Fix - VPS-en, debug**:
```bash
cd /home/ubuntu/ai-agents-hu/mini_projects/gabor.toth

# Naplók nézése
docker-compose logs backend

# Ellenőrizd:
# 1. OPENAI_API_KEY van-e a .env-ben?
# 2. Python szintaxis hibák?
# 3. ChromaDB inicializálása?

# Explicit test
docker-compose up --build backend
# Ctrl+C után

# Port check
netstat -tlnp | grep 8000
```

---

### ❌ "Backend health check passes, de API nem működik"

**OK**: Smoke test-ben "ok" nincs a response-ban

**Fix - VPS-en**:
```bash
# Direct health check tesztje
curl -v http://localhost:8000/api/health

# Expected response:
# {"status":"ok"} vagy {"status":"healthy"}

# Ha üres vagy error:
docker-compose logs backend --tail=50

# Check OPENAI_API_KEY
cat .env | grep OPENAI_API_KEY
```

---

### ❌ "Frontend health check fails"

**OK**: nginx lassú vagy 3000 foglalt

**Fix**:
```bash
# VPS-en, port check
netstat -tlnp | grep 3000

# Ha foglalt, kill
sudo kill -9 <PID>

# Frontend explicit test
docker-compose logs frontend --tail=30

# Nginx config check (container-ben)
docker-compose exec frontend nginx -t
```

---

### ❌ "Smoke test - unexpected backend response"

**OK**: Backend válasza nem tartalmaz "ok" szöveget

**Fix - VPS-en**:
```bash
# Full response check
curl -s http://localhost:8000/api/health | jq .

# Expected structure:
# {
#   "status": "ok",
#   "timestamp": "2026-02-01T..."
# }

# Ha más response:
# 1. Backend verziót check
# 2. API endpoint megváltozott?
# 3. Naplók: docker-compose logs backend
```

---

### ❌ "Deployment Successful, de app nem működik"

**OK**: Health check passed, de logika hiba

**Fix**:
```bash
# Full workflow check
docker-compose ps  # All containers running?

# Logs minden service-ből
docker-compose logs

# Resource użytkownika
docker stats

# Network check
docker network ls
docker inspect <network-name>

# Rollback az előző verzióra:
git log --oneline | head -5
git reset --hard HEAD~1
docker-compose down
docker-compose up -d --build
```

---

### ❌ "Backup failed - no such file"

**OK**: data/users vagy sessions mappa nem létezik (első deploy)

**Fix**: Ez nem hiba, egyszerűen nincs mit backupálni. Workflow folytatódik.

---

### ⚠️ "Frontend health check - timeout (warning)"

**OK**: Frontend 75 másodpercnél lassabb

**Fix - VPS-en**:
```bash
# Frontend naplók
docker-compose logs frontend --tail=30

# Build output check (lehet nagy?)
docker image ls | grep rag-agent

# Resources
docker stats frontend

# Restart explicit
docker-compose restart frontend
docker-compose logs -f frontend
```

---

## ✅ Detailed Deployment Workflow Steps

### Step 1: Pre-Deployment Health Check
```
Ellenőrzi: Van-e működő backend/frontend az update előtt?
Tud: Információs (nem blokkoló)
Oka: Tudni akarjuk, milyen státuszból indulunk
```

### Step 2: Backup Data
```
Biztonsági mentés: data/users és data/sessions
Rollback készítés: Ha probléma van
Tárhelyre: data/.backup_TIMESTAMP/
```

### Step 3: Git Pull
```
Lépés: fetch → checkout main → pull
Timeout: ~2-5 mp
Hiba: Git auth vagy network issue
```

### Step 4: Graceful Docker Update
```
Proces: docker-compose pull → up -d --build
Downtime: ~30-60 mp (build közben)
Stabilizálás: 10 másodperc
```

### Step 5 & 6: Health Checks
```
Backend:  max 30x, 10mp között (300 mp = 5 perc)
Frontend: max 15x, 5mp között (75 mp = 1.25 perc)
Endpoint: /api/health (backend), 5173 root (frontend)
Sikertelen: Logs kiírása, exit 1
```

### Step 7: Smoke Test
```
Tesztel: Backend API response validálása
Keresés: "ok" string a JSON-ben
Oka: Ellenőrzi, hogy nem csak "up", hanem "ready"
```

### Step 8: Logs & Metrics
```
Naplók: docker-compose logs (15 sor/service)
Status: docker-compose ps (container állapota)
CPU/Mem: docker stats (resource usage)
```

---

## 📈 Monitoring Után

### Service státusza:

```bash
# VPS-en:
docker-compose ps
```

### Naplók követése (real-time):

```bash
# Backend naplók
docker-compose logs -f backend

# Frontend naplók
docker-compose logs -f frontend

# Összes service
docker-compose logs -f
```

### Backend health ellenőrzése:

```bash
curl http://localhost:8000/api/health
```

### Frontend elérhetősége:

```bash
curl -I http://localhost:3000
```

### Resource használat:

```bash
# CPU & memória
docker stats

# Lemezhasználat
du -sh data/
```

### Teljes restart (ha kritikus probléma van):

```bash
cd /home/ubuntu/ai-agents-hu/mini_projects/gabor.toth

# Leállítás
docker-compose down

# Friss indítás
docker-compose up -d --build

# Monitoring
docker-compose logs -f
```

### Backup visszaállítása (rollback):

```bash
# Legutóbbi backup mappanevének lekérése
ls -la data/ | grep ".backup_"

# Pl. data/.backup_1704067200
BACKUP_DIR="data/.backup_1704067200"

# Data visszaállítása
cp -r $BACKUP_DIR/users data/ || echo "Nincs users backup"
cp -r $BACKUP_DIR/sessions data/ || echo "Nincs sessions backup"

# Services restart
docker-compose down
docker-compose up -d
```

---

## 🔧 Fejlesztőknek: Workflow Módosítása

Ha változtatsz a workflow-on (pl. más `DEPLOY_PATH`, vagy health check URL):
- Szerkeszd: `mini_projects/gabor.toth/.github/workflows/deploy-local-server.yml`
- Módosítsd az `env` szekciót a tetején
- Git push, majd GitHub Actions futtatás

---

## 📝 Jövőbeli Fejlesztések

### Slack/Discord Notification (opcionális)

Ha szeretnél valós idejű notification-t, add hozzá a workflow-hoz:

**1. Slack Webhook URL készítése:**
   - Slack workspace Settings → Apps & integrations → Incoming Webhooks
   - "Add New Webhook to Workspace"
   - Channel kiválasztása (pl. #deployments)
   - URL kopizálása

**2. GitHub Secrets-hez hozzáadás:**
   - `SLACK_WEBHOOK_URL` = `https://hooks.slack.com/services/T.../B.../X...`

**3. Workflow-hoz hozzáadás (Success):**
```yaml
- name: Notify Slack - Success
  if: success()
  run: |
    curl -X POST ${{ secrets.SLACK_WEBHOOK_URL }} \
      -H 'Content-Type: application/json' \
      -d '{
        "text": "✅ RAG Agent deployment successful!",
        "blocks": [{
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*✅ Deployment Successful*\n📦 RAG Agent\n🌍 Server: ${{ secrets.DEPLOY_HOST }}\n🔗 Backend: http://localhost:8000\n🔗 Frontend: http://localhost:3000"
          }
        }]
      }'
```

**4. Workflow-hoz hozzáadás (Failure):**
```yaml
- name: Notify Slack - Failure
  if: failure()
  run: |
    curl -X POST ${{ secrets.SLACK_WEBHOOK_URL }} \
      -H 'Content-Type: application/json' \
      -d '{
        "text": "❌ RAG Agent deployment FAILED",
        "blocks": [{
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*❌ Deployment Failed*\n📦 RAG Agent\n🌍 Server: ${{ secrets.DEPLOY_HOST }}\n🔗 Check logs: <GitHub Actions URL>"
          }
        }]
      }'
```

---

### Auto-Rollback (opcionális)

Ha szeretnél automatikus rollback-et failure-nél:

```yaml
- name: Rollback on Failure
  if: failure()
  run: |
    ssh -i ~/.ssh/id_rsa ${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }} << 'EOF'
    set -e
    cd ${{ env.DEPLOY_PATH }}
    
    echo "🔄 Rolling back to previous version..."
    git reset --hard HEAD~1
    docker-compose down --remove-orphans
    docker-compose up -d --build
    
    sleep 10
    if curl -s http://localhost:8000/api/health > /dev/null; then
      echo "✅ Rollback successful!"
    else
      echo "❌ Rollback failed too!"
    fi
    EOF
```

---

### Email Notification (opcionális)

GitHub Actions beépített email funkciót használ - ha notification kell, a workflow `continue-on-error` vagy `failure()` step végzéshez email érkezik.

---

## ✅ Checklist - Mielőtt Deploy-olsz

- [ ] VPS SSH key be van állítva
- [ ] GitHub Secrets feltöltve: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
- [ ] VPS-en `.env` fájl létezik az `OPENAI_API_KEY`-vel
- [ ] Docker & Docker Compose fut a VPS-en
- [ ] Repository klónozva a VPS-en a megadott útvonalra
- [ ] Git pull-t tudsz csinálni manuálisan (`git pull origin main`)
- [ ] `curl http://localhost:8000/api/health` működik lokálisan

---

## 📞 Support

Ha probléma van, nézd meg:
1. GitHub Actions logok: Actions tab → workflow run → output
2. VPS-en: `docker-compose logs`
3. SSH elérhetőség: `ssh -i ~/.ssh/id_github_rag ubuntu@YOUR_VPS_IP`

---

**Készült**: 2026. február  
**Verzió**: 1.0  
**Szerző**: RAG Agent Deployment System
