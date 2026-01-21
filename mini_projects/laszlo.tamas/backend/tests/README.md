# Knowledge Router PROD - Test Suite

Automated test infrastructure using **pytest** for the Knowledge Router system.

---

## 📁 Test Structure

```
tests/
├── unit/              # Fast, isolated unit tests (mocked dependencies)
├── integration/       # DB + Qdrant + external service tests
└── e2e/              # Full workflow end-to-end tests
```

---

## 🚀 Running Tests

### Prerequisites

```powershell
# 1. Start Docker services
docker-compose up -d

# 2. Load seed data (if not already loaded)
docker exec -i knowledge_router_postgres psql -U postgres -d knowledge_router < data/seed/00_basic_data.sql
```

### Run All Tests (Mocked - No OpenAI Cost)

```powershell
# Run all tests with mocked OpenAI
docker-compose exec backend pytest tests/ -v

# With coverage report
docker-compose exec backend pytest tests/ --cov=. --cov-report=term-missing
```

### Run Tests by Category

```powershell
# Unit tests only (fast)
docker-compose exec backend pytest tests/unit/ -v

# Integration tests only
docker-compose exec backend pytest tests/integration/ -v

# E2E tests only
docker-compose exec backend pytest tests/e2e/ -v
```

### Run Tests with Real OpenAI API

⚠️ **WARNING:** This will incur OpenAI API costs (~$0.01-0.05 per full test run)

```powershell
# Run ALL tests including real OpenAI calls
docker-compose exec backend pytest tests/ --run-openai -v

# Run only OpenAI tests
docker-compose exec backend pytest tests/ -m openai --run-openai -v
```

### Run Specific Test Files

```powershell
# Workflow tests
docker-compose exec backend pytest tests/e2e/test_chat_workflow.py -v

# API endpoint tests
docker-compose exec backend pytest tests/e2e/test_api_endpoints.py -v

# Document RAG pipeline tests
docker-compose exec backend pytest tests/integration/test_document_rag.py -v
```

### Run Tests by Marker

```powershell
# Integration tests only
docker-compose exec backend pytest -m integration -v

# E2E tests only
docker-compose exec backend pytest -m e2e -v

# Slow tests
docker-compose exec backend pytest -m slow -v

# Exclude OpenAI tests (default behavior)
docker-compose exec backend pytest -m "not openai" -v
```

---

## 🏷️ Test Markers

| Marker | Description | OpenAI Cost |
|--------|-------------|-------------|
| `@pytest.mark.unit` | Unit test (mocked) | $0 |
| `@pytest.mark.integration` | Integration test | $0 (mocked) |
| `@pytest.mark.e2e` | End-to-end test | $0 (mocked) |
| `@pytest.mark.openai` | Real OpenAI API call | **$0.001-0.005** |
| `@pytest.mark.slow` | Test takes >5s | Varies |

**Default:** All `@pytest.mark.openai` tests are **skipped** unless you use `--run-openai` flag.

---

## 🔧 Test Fixtures

### Core Fixtures (from `conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `db_session` | function | PostgreSQL connection with auto-rollback |
| `qdrant_client` | session | Qdrant client |
| `test_client` | function | FastAPI TestClient |
| `mock_openai_chat_completion` | function | Mock OpenAI chat (no cost) |
| `mock_openai_embedding` | function | Mock OpenAI embeddings (no cost) |
| `test_tenant_user` | function | Seeded tenant_id=1, user_id=1 |
| `test_session` | function | Test chat session |
| `test_document` | function | Test document with chunks |
| `clean_qdrant_collection` | function | Isolated test Qdrant collection |

---

## 📊 Coverage

**Target:** 70% minimum (configured in `pytest.ini`)

### Generate Coverage Report

```powershell
# Terminal report
docker-compose exec backend pytest tests/ --cov=. --cov-report=term-missing

# HTML report (opens in browser)
docker-compose exec backend pytest tests/ --cov=. --cov-report=html
# View at: backend/htmlcov/index.html

# XML report (for CI/CD)
docker-compose exec backend pytest tests/ --cov=. --cov-report=xml
```

---

## 💰 Cost Management

### OpenAI API Costs per Test

| Test | Type | Est. Cost |
|------|------|-----------|
| `test_chat_branch_greeting` | Chat completion | $0.001 |
| `test_rag_branch_document_query` | Embedding + completion | $0.002-0.005 |
| `test_generate_embedding_real` | Embedding | $0.0001 |
| `test_full_rag_pipeline` | Multiple embeddings | $0.001 |
| **Full test suite with `--run-openai`** | All real API calls | **~$0.02-0.05** |

### Cost Optimization Strategy

1. **Default:** All tests run with **mocked OpenAI** → $0 cost
2. **CI/CD:** Run mocked tests only → $0 cost
3. **Pre-deployment:** Run `--run-openai` once → ~$0.05 cost
4. **Debug:** Run specific OpenAI test with `-k test_name`

---

## 🔍 Test Development Guidelines

### Writing Unit Tests

```python
@pytest.mark.unit
def test_my_function(mock_openai_chat_completion):
    """Test function with mocked dependencies."""
    result = my_function()
    assert result == expected
```

### Writing Integration Tests

```python
@pytest.mark.integration
def test_database_operation(db_session, test_tenant_user):
    """Test DB operation with real database."""
    result = insert_data(test_tenant_user["user_id"])
    assert result is not None
```

### Writing E2E Tests with Real OpenAI

```python
@pytest.mark.e2e
@pytest.mark.openai  # Mark as OpenAI test
@pytest.mark.slow    # Mark as slow
def test_workflow_real(workflow, test_session):
    """
    Test workflow with real OpenAI API.
    
    Real OpenAI call - costs ~$0.001
    """
    result = workflow.execute(...)
    assert result["final_answer"] is not None
```

---

## 🐛 Debugging Failed Tests

### Verbose Output

```powershell
# Show print statements
docker-compose exec backend pytest tests/ -v -s

# Show full traceback
docker-compose exec backend pytest tests/ --tb=long
```

### Run Single Test

```powershell
# Specific test function
docker-compose exec backend pytest tests/e2e/test_chat_workflow.py::TestUnifiedChatWorkflow::test_workflow_compiles -v
```

### Drop into Debugger on Failure

```powershell
docker-compose exec backend pytest tests/ --pdb
```

---

## 📝 Test Data

**Seeded data** (from `data/seed/00_basic_data.sql`):
- **Tenant ID:** 1 (Acme Corp)
- **User ID:** 1 (Alice), 2 (Bob)

**Test fixtures create:**
- Isolated sessions
- Test documents
- Test Qdrant collections (auto-cleaned)

**Database isolation:**
- Each test uses **transaction rollback** → no permanent changes
- Qdrant tests use **separate test collections** → isolated

---

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start services
        run: docker-compose up -d
      
      - name: Wait for services
        run: sleep 10
      
      - name: Run tests (mocked)
        run: docker-compose exec -T backend pytest tests/ --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./backend/coverage.xml
```

---

## 🆚 Tests vs. Debug Scripts

| Aspect | `tests/` | `debug/` |
|--------|----------|----------|
| Purpose | Automated verification | Manual diagnostics |
| Framework | pytest | Standalone scripts |
| Assertions | pytest assertions | print statements |
| CI/CD | Yes | No |
| Coverage | Yes | No |
| Isolation | Transaction rollback | Direct DB |

**Migration status:**
- ✅ `debug/test_unified_workflow.py` → `tests/e2e/test_chat_workflow.py`
- ✅ `debug/test_api_endpoints.py` → `tests/e2e/test_api_endpoints.py`
- ✅ `debug/test_full_retrieval.py` → `tests/integration/test_document_rag.py`
- ⏸️ `debug/check_*.py` scripts remain for diagnostics

---

## 📚 Further Reading

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)

---

**Last Updated:** 2026-01-12  
**Coverage Target:** 70%  
**Test Count:** 40+ tests across unit/integration/e2e
