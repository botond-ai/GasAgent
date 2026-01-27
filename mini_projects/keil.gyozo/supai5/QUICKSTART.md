# 🚀 SupportAI Quick Start Guide

## Step 1: Setup Environment

```powershell
# Copy environment template
cp .env.example .env

# Open .env in editor
notepad .env

# Add your OpenAI API key:
OPENAI_API_KEY=sk-your-key-here

# (Optional) Add Cohere key for better reranking:
COHERE_API_KEY=your-cohere-key-here
```

## Step 2: Start Services

```powershell
# Start all containers
docker compose up -d

# Wait ~30 seconds for services to initialize
```

## Step 3: Verify Health

```powershell
# Check container status
docker ps

# Should show 4 containers:
# - supai5-frontend
# - supai5-backend
# - supai5-qdrant
# - supai5-redis

# Check backend health
curl http://localhost:8000/health
```

## Step 4: Access UI

Open browser to: **http://localhost:5173**

## Step 5: Create Test Ticket

1. Click **"+ New Ticket"** button
2. Fill in form:
   - Customer Name: `John Doe`
   - Email: `john@example.com`
   - Subject: `Billing issue with recent charge`
   - Message: `I was charged twice for my subscription last month`
3. Click **"Create Ticket"**
4. Click **"Process with AI"**
5. Wait 10-30 seconds for AI processing

## Step 6: Review Results

The processed ticket will show:

- ✅ **Triage**: Category, Priority, SLA, Team assignment
- ✅ **AI Draft**: Greeting, body, closing
- ✅ **Citations**: Knowledge base sources
- ✅ **Policy Check**: Compliance validation

## Common Commands

```powershell
# View logs
docker logs supai5-backend -f

# Stop all services
docker compose down

# Full reset (delete all data)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

## Troubleshooting

### "Connection refused" error

Wait 30-60 seconds for services to fully start.

### Qdrant shows "unhealthy"

```powershell
docker compose down -v
docker compose up --build
```

### Frontend shows blank page

Check browser console for errors. Verify backend is running:

```powershell
curl http://localhost:8000/health
```

## Next Steps

- 📚 Read full [README.md](README.md)
- 🔧 Configure RAG parameters in `.env`
- 📊 Load knowledge base documents
- 🧪 Run tests: `docker exec supai5-backend pytest`

---

Need help? Check logs: `docker logs supai5-backend -f`
