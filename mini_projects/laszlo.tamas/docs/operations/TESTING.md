# Testing Guide - Knowledge Router

## Mit csinál (felhasználói nézőpont)

Komprehenzív testing stratégia unit test-ektől integration és load testing-ig. Automated testing pipeline Docker környezetben, pytest framework-kel és coverage jelentésekkel.

## Használat

### Test suite futtatása
```bash
# Minden test futtatása
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Unit testek csak
pytest backend/tests/unit/ -v

# Integration testek
pytest backend/tests/integration/ -v --maxfail=1

# Coverage jelentés
pytest --cov=backend --cov-report=html --cov-report=term
```

### Load testing
```bash
# Locust performance testing
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Artillery load test
artillery run tests/load/artillery-config.yml
```

### Manual testing
```bash
# API endpoint testing
python backend/debug/test_api.py

# Document upload test
python backend/debug/test_upload.py

# Memory system test
python backend/debug/test_memory.py
```

## Technikai implementáció

### Test Environment Setup
```yaml
# docker-compose.test.yml
version: '3.8'

services:
  test-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: knowledge-router-test-backend
    environment:
      - ENVIRONMENT=testing
      - DATABASE_URL=postgresql://test_user:test_pass@test-postgres:5432/k_r_test
      - QDRANT_URL=http://test-qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=redis://test-redis:6379/0
    depends_on:
      - test-postgres
      - test-qdrant
      - test-redis
    command: |
      sh -c "
        python -m pytest tests/ -v \
          --cov=backend \
          --cov-report=html:/app/htmlcov \
          --cov-report=term \
          --cov-report=xml:/app/coverage.xml \
          --junitxml=/app/junit.xml
      "
    volumes:
      - ./backend:/app
      - test-coverage:/app/htmlcov
    networks:
      - test-network

  test-postgres:
    image: postgres:15
    container_name: knowledge-router-test-postgres
    environment:
      - POSTGRES_DB=k_r_test
      - POSTGRES_USER=test_user
      - POSTGRES_PASSWORD=test_pass
    volumes:
      - ./backend/database/migrations:/docker-entrypoint-initdb.d
    networks:
      - test-network

  test-qdrant:
    image: qdrant/qdrant:latest
    container_name: knowledge-router-test-qdrant
    networks:
      - test-network

  test-redis:
    image: redis:7-alpine
    container_name: knowledge-router-test-redis
    networks:
      - test-network

volumes:
  test-coverage:

networks:
  test-network:
    driver: bridge
```

### Unit Tests
```python
# tests/unit/test_chat_workflow.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from services.unified_chat_workflow import UnifiedChatWorkflow
from database.models import ChatState

class TestUnifiedChatWorkflow:
    """Unit tests for chat workflow."""
    
    @pytest.fixture
    def workflow(self):
        return UnifiedChatWorkflow()
    
    @pytest.fixture
    def mock_state(self):
        return ChatState(
            query="Test query",
            tenant_id=1,
            user_id=1,
            session_id="test-session",
            chat_history=[],
            reasoning=None,
            tool_calls=[],
            final_answer=""
        )
    
    @pytest.mark.asyncio
    async def test_reasoning_node(self, workflow, mock_state):
        """Test reasoning node logic."""
        
        # Mock LLM response
        mock_reasoning = Mock()
        mock_reasoning.intent = "information_request"
        mock_reasoning.confidence = 0.95
        mock_reasoning.needs_tools = True
        
        with patch.object(workflow.llm_service, 'analyze_query', return_value=mock_reasoning):
            result_state = await workflow._reasoning_node(mock_state)
            
            assert result_state.reasoning == mock_reasoning
            assert result_state.reasoning.intent == "information_request"
            assert result_state.reasoning.needs_tools is True
    
    @pytest.mark.asyncio
    async def test_tool_execution_node(self, workflow, mock_state):
        """Test tool execution node."""
        
        # Setup state with reasoning
        mock_reasoning = Mock()
        mock_reasoning.intent = "document_search"
        mock_reasoning.search_terms = ["policy", "remote work"]
        
        mock_state.reasoning = mock_reasoning
        
        # Mock document search
        mock_search_results = [
            Mock(content="Remote work policy...", document_id=1, relevance_score=0.95)
        ]
        
        with patch.object(workflow.qdrant_service, 'search_documents', return_value=mock_search_results):
            result_state = await workflow._tool_execution_node(mock_state)
            
            assert len(result_state.tool_calls) > 0
            assert result_state.tool_calls[0].tool_name == "document_search"
            assert result_state.tool_calls[0].status == "completed"
    
    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, workflow, mock_state):
        """Test error handling in workflow."""
        
        # Mock LLM failure
        with patch.object(workflow.llm_service, 'analyze_query', side_effect=Exception("LLM API error")):
            with pytest.raises(Exception, match="LLM API error"):
                await workflow._reasoning_node(mock_state)
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, workflow):
        """Test tenant isolation in workflow."""
        
        state1 = ChatState(query="Test", tenant_id=1, user_id=1, session_id="s1")
        state2 = ChatState(query="Test", tenant_id=2, user_id=2, session_id="s2")
        
        # Mock different results for different tenants
        with patch.object(workflow.qdrant_service, 'search_documents') as mock_search:
            mock_search.side_effect = [
                [Mock(content="Tenant 1 doc", document_id=1)],  # Tenant 1
                [Mock(content="Tenant 2 doc", document_id=2)]   # Tenant 2
            ]
            
            result1 = await workflow._tool_execution_node(state1)
            result2 = await workflow._tool_execution_node(state2)
            
            # Verify different results
            assert result1.tool_calls[0].results != result2.tool_calls[0].results
            
            # Verify correct tenant IDs were passed
            calls = mock_search.call_args_list
            assert calls[0][1]['tenant_id'] == 1
            assert calls[1][1]['tenant_id'] == 2
```

### Integration Tests
```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from main import app
from database.pg_init import init_database

class TestAPIEndpoints:
    """Integration tests for API endpoints."""
    
    @pytest.fixture(scope="session")
    async def setup_test_db(self):
        """Setup test database."""
        await init_database()
        yield
        # Cleanup handled by test containers
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data
    
    @pytest.mark.asyncio
    async def test_chat_endpoint(self, async_client, setup_test_db):
        """Test chat processing endpoint."""
        
        request_data = {
            "query": "What is the remote work policy?",
            "user_context": {
                "tenant_id": 1,
                "user_id": 1
            }
        }
        
        response = await async_client.post("/api/chat/", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "final_answer" in data
        assert "session_id" in data
        assert "execution_time_ms" in data
        assert data["execution_time_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_document_upload(self, async_client, setup_test_db):
        """Test document upload and processing."""
        
        # Create test document
        test_content = b"This is a test document for upload testing."
        
        files = {"file": ("test.txt", test_content, "text/plain")}
        data = {"tenant_id": 1, "visibility": "tenant"}
        
        response = await async_client.post(
            "/api/workflows/document-processing",
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        
        result = response.json()
        assert "document_id" in result
        assert "chunks_created" in result
        assert result["chunks_created"] > 0
    
    @pytest.mark.asyncio
    async def test_memory_management(self, async_client, setup_test_db):
        """Test memory creation and search."""
        
        # Create memory
        memory_data = {
            "content": "Alice prefers coffee over tea",
            "memory_type": "explicit_fact"
        }
        
        response = await async_client.post("/api/memory/", json=memory_data)
        assert response.status_code == 200
        
        memory = response.json()
        assert "id" in memory
        assert memory["content"] == memory_data["content"]
        
        # Search memory
        search_response = await async_client.get(
            "/api/memory/search?query=Alice coffee&tenant_id=1&user_id=1"
        )
        assert search_response.status_code == 200
        
        search_results = search_response.json()
        assert len(search_results) > 0
        assert search_results[0]["content"] == memory_data["content"]
```

### Load Testing
```python
# tests/load/locustfile.py
from locust import HttpUser, task, between
import json
import random

class KnowledgeRouterUser(HttpUser):
    """Locust user for load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup test user."""
        self.tenant_id = random.randint(1, 5)
        self.user_id = random.randint(1, 100)
        
    @task(3)
    def chat_query(self):
        """Test chat endpoint."""
        
        queries = [
            "What is the company policy on remote work?",
            "How do I request vacation time?", 
            "What are the office hours?",
            "Tell me about the employee benefits",
            "What is the dress code policy?"
        ]
        
        request_data = {
            "query": random.choice(queries),
            "user_context": {
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            }
        }
        
        with self.client.post(
            "/api/chat/",
            json=request_data,
            catch_response=True,
            name="chat_query"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "final_answer" in data:
                    response.success()
                else:
                    response.failure("Missing final_answer in response")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def memory_search(self):
        """Test memory search endpoint."""
        
        search_queries = [
            "preferences", "settings", "user info", 
            "previous conversations", "stored facts"
        ]
        
        with self.client.get(
            f"/api/memory/search?query={random.choice(search_queries)}&tenant_id={self.tenant_id}&user_id={self.user_id}",
            catch_response=True,
            name="memory_search"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Test health endpoint."""
        
        with self.client.get("/health/", name="health_check") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
```

### Test Configuration
```python
# tests/conftest.py
import pytest
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models import Base

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", 
    "postgresql+asyncpg://test_user:test_pass@localhost:5432/k_r_test"
)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def async_engine():
    """Create async database engine for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def db_session(async_engine):
    """Create database session for testing."""
    Session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with Session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def override_get_db(db_session):
    """Override database dependency for testing."""
    from api.dependencies import get_db
    
    def _override_get_db():
        return db_session
    
    return _override_get_db
```

## Funkció-specifikus konfiguráció

```ini
# Test settings
TEST_DATABASE_URL=postgresql+asyncpg://test_user:test_pass@test-postgres:5432/k_r_test
TEST_QDRANT_URL=http://test-qdrant:6333
TEST_REDIS_URL=redis://test-redis:6379/0

# Coverage settings
COVERAGE_MIN_PERCENTAGE=85
COVERAGE_REPORT_DIR=htmlcov

# Load testing
LOCUST_USERS=50
LOCUST_SPAWN_RATE=5
LOCUST_RUN_TIME=300s

# Performance thresholds
MAX_RESPONSE_TIME_MS=5000
MIN_SUCCESS_RATE=99.5
MAX_ERROR_RATE=0.5
```

### CI/CD Test Integration
```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Run test suite
      run: |
        docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
        fail_ci_if_error: true
    
    - name: Archive test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: |
          backend/junit.xml
          backend/htmlcov/
```