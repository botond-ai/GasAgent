# SupportAI - Multi-Tool Agent System

A comprehensive AI-powered customer support ticketing system built with LangGraph, FastAPI, and React. This application processes user support requests through a sophisticated forced sequence of tools, creating structured tickets with full GDPR compliance.

## 🎯 Overview

This application implements a **Support Feedback Workflow** that automatically:

1. ❓ **Understands** the user's issue using RAG-based document search
2. 😊 **Analyzes sentiment** of the user's message
3. 🌐 **Responds in the user's language** with weather-based small talk
4. 📖 **Provides information** from the knowledge base
5. �️ **Classifies urgency** and assigns priority
6. ⏰ **Commits resolution deadline** based on SLA
7. 💰 **Calculates costs** and converts to multiple currencies
8. 🛡️ **Masks personal data** for GDPR/legal compliance
9. 🏗️ **Structures conversation** into a JSON ticket
10. 💾 **Stores data** in SQLite database and pCloud storage
11. 📧 **Notifies the team** via email
12. 📊 **Displays tickets** on a dashboard

## ✨ Key Features

### 13+ Integrated Tools
| Tool | Purpose | API/Technology |
|------|---------|----------------|
| 🌐 **Translator** | Language detection & translation | OpenAI GPT + Lingua |
| 😊 **Sentiment** | Emotional tone analysis | OpenAI GPT |
| ☀️ **Weather** | Current weather for greetings | Open-Meteo |
| � **Documents (RAG)** | Issue identification from KB | FAISS + LangChain |
| 💱 **FX Rates** | Currency conversion | ExchangeRate.host |
| 🛡️ **Guardrails** | PII masking for GDPR | Regex patterns |
| 🏗️ **JSON Creator** | Structured ticket creation | Local |
| � **Photo Upload** | Attachment storage | pCloud API |
| 💾 **SQLite Save** | Database persistence | SQLite |
| � **Email Send** | Team notifications | Gmail SMTP |
| 📻 **Radio** | Radio station search | Radio Browser API |
| ₿ **Crypto** | Cryptocurrency prices | CoinGecko |
| �️ **Geocode** | Address to coordinates | Nominatim |

### Monitoring & Analytics
- **Prometheus** metrics collection (port 9090)
- **Grafana** dashboards (port 3001)
- Ticket statistics, cost analytics, tool performance tracking

---

## ⚙️ Forced Tool Sequence

When a support issue is detected, the system executes this predefined sequence:

```
User Message
│
▼
┌─────────────────────┐
│ Detect Support Issue│ ◄── Keyword matching + short message detection
└──────────┬──────────┘
           │ YES
           ▼
┌─────────────────────┐
│ 1. Translator       │ ◄── Translate to English if needed
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. Sentiment        │ ◄── Analyze emotional tone
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. Weather          │ ◄── Get weather for greeting
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 4. Documents (RAG)  │ ◄── Identify issue type from knowledge base
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 5. FX Rates USD→EUR │ ◄── Convert cost to EUR
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 6. FX Rates USD→HUF │ ◄── Convert cost to HUF
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 7. Final Response   │ ◄── Generate warm, helpful response
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 8. Guardrails       │ ◄── Mask PII for GDPR compliance
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 9. JSON Creator     │ ◄── Create structured ticket
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 10. Photo Upload    │ ◄── Upload attachments to pCloud
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 11. SQLite Save     │ ◄── Save ticket to database
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 12. Email Send      │ ◄── Notify team via email
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 13. Dashboard       │ ◄── View all tickets
└─────────────────────┘
```

---

## 🏛️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Chat Window │  │ View Tickets│  │ Debug Panel │  │ File Upload │ │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └──────┬──────┘ │
└─────────┼────────────────┼──────────────────────────────────┼───────┘
          │                │                                  │
          ▼                ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      ChatService                                 ││
│  │  • Process messages    • Manage sessions    • Build memory      ││
│  └──────────────────────────────┬──────────────────────────────────┘│
│                                 │                                    │
│  ┌──────────────────────────────▼──────────────────────────────────┐│
│  │                        AIAgent (LangGraph)                       ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  ││
│  │  │agent_decide │──│ tool_nodes  │──│   agent_finalize        │  ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                 │                                    │
│  ┌──────────────────────────────▼──────────────────────────────────┐│
│  │                          TOOLS (13+)                             ││
│  │  Translator│Sentiment│Documents│Weather│FX_Rates│Guardrails     ││
│  │  JSON_Creator│SQLite_Save│Photo_Upload│Email_Send│Radio│Crypto  ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ SQLite   │    │  pCloud  │    │  Gmail   │    │ External │
    │ Database │    │ Storage  │    │  SMTP    │    │   APIs   │
    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, CSS |
| Backend | FastAPI, Python 3.11 |
| AI Framework | LangGraph, LangChain |
| LLM | OpenAI GPT-4 Turbo |
| Vector DB | FAISS |
| Database | SQLite |
| Cloud Storage | pCloud API |
| Email | Gmail SMTP |
| Monitoring | Prometheus, Grafana |
| Containerization | Docker, Docker Compose |

### Backend Structure

```
backend/
├── domain/                 # Domain layer - Core business entities
│   ├── models.py          # Data models (Message, UserProfile, Memory, ToolCall, etc.)
│   └── interfaces.py      # Abstract interfaces (IUserRepository, IToolClient, etc.)
├── infrastructure/        # Infrastructure layer - External implementations
│   ├── repositories.py    # File-based persistence (user profiles, conversations)
│   ├── tool_clients.py    # External API clients (weather, crypto, FX, RAG, etc.)
│   ├── smtp_client.py     # Gmail SMTP client for email notifications
│   ├── metrics.py         # Prometheus metrics collection
│   └── error_handlers.py  # Global exception handling
├── services/              # Service layer - Business logic
│   ├── agent.py           # LangGraph agent implementation with forced tool sequence
│   ├── tools.py           # 13+ tool wrappers (Guardrails, JSON Creator, etc.)
│   └── chat_service.py    # Chat workflow orchestration
├── templates/             # Jinja2 templates for tickets dashboard
└── main.py               # API layer - FastAPI endpoints
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **OpenAI API Key**

### Quick Start with Docker (Recommended)

```bash
cd Application
docker-compose up -d
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| Tickets Dashboard | http://localhost:8000/tickets | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3001 | admin / supportai123 |

---

## 🔒 Environment Variables

Create a `.env` file in the Application folder:

```env
# Required
OPENAI_API_KEY=your_openai_api_key

# pCloud Storage (for photo uploads)
PCLOUD_USERNAME=your_pcloud_username
PCLOUD_PASSWORD=your_pcloud_password
PCLOUD_ACCESS_TOKEN=your_pcloud_token
PCLOUD_ENDPOINT=eapi
PCLOUD_PHOTO_MEMORIES_FOLDER_ID=your_folder_id

# Gmail SMTP (for email notifications)
GMAIL_USERNAME=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_app_password
GMAIL_SMTP_SERVER=smtp.gmail.com
GMAIL_SMTP_PORT=587
GMAIL_TO_EMAIL=recipient@email.com

# RAG Re-ranker (optional)
RERANKER_TYPE=llm
COHERE_API_KEY=your_cohere_key
```

---

## 🛡️ Guardrails - PII Masking

The Guardrails tool automatically masks sensitive personal information for GDPR compliance:

| PII Type | Mask |
|----------|------|
| Email addresses | `###EMAIL###` |
| Phone numbers | `###PHONE###` |
| Credit card numbers | `###CREDIT_CARD###` |
| Social Security Numbers | `###SSN###` |
| National IDs | `###NATIONAL_ID###` |
| IP addresses | `###IP###` |
| IBAN bank accounts | `###IBAN###` |
| Dates of birth | `###DOB###` |
| Passport numbers | `###PASSPORT###` |
| Physical addresses | `###ADDRESS###` |
| Tax IDs | `###TAX_ID###` |

---

## 📊 Monitoring

### Prometheus Metrics

The application exposes metrics at `/metrics`:
- 🎫 Ticket statistics (total, by priority, sentiment, issue type)
- 💰 Cost analytics (OpenAI API costs, ticket costs)
- 🔧 Tool performance (invocations, execution time, success rate)
- 📡 HTTP request metrics (rate, latency, status codes)
- 🌐 Language & sentiment distribution
- 🔢 Token usage tracking

### Grafana Dashboards

Pre-configured dashboards include:
1. **Overview** - Key metrics at a glance
2. **Ticket Analytics** - Priority, sentiment, issue type distribution
3. **Tool Performance** - Invocations, execution time, success rates
4. **Cost Analytics** - OpenAI costs, token usage, ticket costs
5. **Language & Sentiment** - Message languages, translations
6. **HTTP Requests** - Request rates, latencies, status codes

---

## 📚 API Endpoints

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Process chat message |
| POST | `/api/chat/upload` | Process chat with file attachments |
| GET | `/api/session/{session_id}` | Get conversation history |
| GET | `/api/history/search?q=query` | Search conversation history |

### Profile Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile/{user_id}` | Get user profile |
| PUT | `/api/profile/{user_id}` | Update user profile |

### Ticket Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tickets` | View tickets dashboard (HTML) |
| GET | `/api/tickets` | Get all tickets (JSON) |
| GET | `/api/tickets/{ticket_number}` | Get specific ticket |

### Monitoring Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/metrics` | Prometheus metrics |
| GET | `/` | Health check |

---

## 📂 Data Storage

```
data/
├── users/           # User profiles (never deleted)
│   └── user_123.json
├── sessions/        # Conversation histories
│   └── session_456.json
├── tickets/         # JSON ticket files
│   └── TK20260130_001/
│       ├── ticket.json
│       └── attachments/
└── tickets.db       # SQLite database
```

---

## 🧪 Testing

Test scripts are available in the `Test_Scripts_And_Logs` folder:

```bash
# Run all tests
pip install -r requirements.txt
pytest Test_Scripts_And_Logs/

# Individual test suites
python Test_Scripts_And_Logs/test_pydantic_api.py      # API tests
python Test_Scripts_And_Logs/test_selenium_ui.py       # UI tests
python Test_Scripts_And_Logs/test_unit_ai_functions.py # Unit tests
```

---

## 📈 Documentation

- **langraph.md** - Comprehensive LangGraph workflow documentation
- **readme.md** (root) - Project overview and quick start
- **requirements.txt** - All Python dependencies with comments

---

## 🛠️ Technologies

### Backend
- **FastAPI** - Modern async web framework
- **LangGraph** - Agent orchestration and workflow
- **LangChain** - LLM integration utilities
- **OpenAI** - GPT-4 Turbo for reasoning
- **FAISS** - Vector database for RAG
- **SQLite** - Ticket persistence
- **Prometheus Client** - Metrics collection

### Frontend
- **React 18** - UI library
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool
- **Axios** - HTTP client

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy
- **Prometheus** - Metrics collection
- **Grafana** - Metrics visualization

---

**Built for the AI Agent Programming Course - Homework 4**
