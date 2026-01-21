# Knowledge Router - Dokumentáció

## 🎯 Áttekintés

Átfogó dokumentáció a Knowledge Router multi-tenant RAG rendszerhez. LangGraph workflow orchestration, real-time chat interface és enterprise-grade monitoring.

---

## 📚 Dokumentációs struktúra

### 🏗️ [Architecture](architecture/)
- [**SYSTEM_OVERVIEW.md**](architecture/SYSTEM_OVERVIEW.md) - 4-rétegű architektúra + tech stack
- [**DATABASE_SCHEMA.md**](architecture/DATABASE_SCHEMA.md) - Multi-tenant DB design + táblák
- [**WORKFLOW_DIAGRAM.md**](architecture/WORKFLOW_DIAGRAM.md) - LangGraph flow + decision points
- [**NODE_REFERENCE.md**](architecture/NODE_REFERENCE.md) - Node catalog + parallel execution

### ⚙️ [Features](features/)
- [**chat-workflow.md**](features/chat-workflow.md) - Chat endpoint + LangGraph state management
- [**document-processing.md**](features/document-processing.md) - Upload, chunking, RAG architecture
- [**hybrid-search.md**](features/hybrid-search.md) - Vector + keyword search + reranking
- [**memory-management.md**](features/memory-management.md) - Long-term memory + consolidation
- [**query-optimization.md**](features/query-optimization.md) - Query rewrite logic + cache
- [**llm-configuration.md**](features/llm-configuration.md) - Triple LLM setup + temperature settings
- [**caching.md**](features/caching.md) - Semantic + exact cache implementation
- [**workflow-tracking.md**](features/workflow-tracking.md) - Historical node execution analysis
- [**excel-tools.md**](features/excel-tools.md) - MCP server Excel operations
- [**external-apis.md**](features/external-apis.md) - Weather, Currency, GitHub tools
- [**error-handling.md**](features/error-handling.md) - Retry patterns + fallback strategies
- [**user-context.md**](features/user-context.md) - Timezone handling + tenant context
- [**api-security.md**](features/api-security.md) - Rate limiting + allow API config
- [**debug-panel.md**](features/debug-panel.md) - Frontend debugging tools

### 📡 [Observability](observability/)
- [**PROMETHEUS_GRAFANA.md**](observability/PROMETHEUS_GRAFANA.md) - Metrics + dashboards
- [**LOKI_LOGGING.md**](observability/LOKI_LOGGING.md) - Log aggregation + structured format
- [**TEMPO_TRACING.md**](observability/TEMPO_TRACING.md) - Distributed tracing setup
- [**ALERTMANAGER.md**](observability/ALERTMANAGER.md) - Alert config + notifications

### 🌐 [API](api/)
- [**API_REFERENCE.md**](api/API_REFERENCE.md) - Complete REST API documentation

### 🚀 [Operations](operations/)
- [**DEPLOYMENT.md**](operations/DEPLOYMENT.md) - Docker setup + startup/reset sequences
- [**TESTING.md**](operations/TESTING.md) - Pytest patterns + test data recommendations
- [**TROUBLESHOOTING.md**](operations/TROUBLESHOOTING.md) - Common issues + debug workflows

---

## 🚀 Quick Navigation

### Fejlesztő onboarding
1. [README.md](../README.md) - Gyors indítás
2. [DEPLOYMENT.md](operations/DEPLOYMENT.md) - Setup részletek
3. [SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) - Architektúra megértés

### Feature implementáció
1. [NODE_REFERENCE.md](architecture/NODE_REFERENCE.md) - Workflow nodes
2. [API_REFERENCE.md](api/API_REFERENCE.md) - API endpoints
3. [TESTING.md](operations/TESTING.md) - Test patterns

### Production deployment  
1. [DEPLOYMENT.md](operations/DEPLOYMENT.md) - Docker + environment
2. [PROMETHEUS_GRAFANA.md](observability/PROMETHEUS_GRAFANA.md) - Monitoring setup
3. [TROUBLESHOOTING.md](operations/TROUBLESHOOTING.md) - Issue resolution

---

## 📊 Dokumentáció státusz

| Kategória | Dokumentumok | Státusz |
|-----------|-------------|---------|
| Core Setup | 3/3 | ✅ Kész |
| Architecture | 0/4 | 🔄 Folyamatban |
| Features | 0/14 | ⏳ Tervezés alatt |
| Observability | 0/4 | ⏳ Tervezés alatt |
| Operations | 0/3 | ⏳ Tervezés alatt |

**Utolsó frissítés:** 2026-01-21  
**Készítő:** GitHub Copilot  
**Template:** [Project Documentation Structure SKILL](../../.github/skills/project-documentation-structure/SKILL.md)