"""
Contract tests for /chat endpoint.

Why this module exists:
- Validates chat response schema and structure
- Tests chat with fake LLM and fake embeddings (no OpenAI calls)
- Verifies source attribution format

Design decisions:
- Create temp vector store with fake embeddings
- Inject fake LLM to avoid OpenAI API calls
- Verify response structure matches Pydantic schema
"""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.rag.chain import create_chat_llm
from app.rag.embeddings import create_embeddings
from app.tests.test_fakes import FakeEmbeddings, FakeLLM


def test_chat_contract_with_fake_llm():
    """
    Test /chat endpoint contract with fake LLM and embeddings.

    Why this test: Validates that chat response has correct structure:
    - answer is non-empty string
    - sources is list of SourceAttribution objects
    - model field matches config
    - session_id is echoed back

    Why fake LLM/embeddings: Avoids OpenAI API calls during testing.
    Tests contract regardless of actual LLM response content.
    """
    # Assert: Response must match ChatResponse schema

    with tempfile.TemporaryDirectory() as temp_docs_dir, \
         tempfile.TemporaryDirectory() as temp_vs_dir:

        # Create test markdown file
        test_file = Path(temp_docs_dir) / "test.md"
        test_file.write_text("# Test Document\n\nThis is a test document for contract testing.")

        test_settings = Settings(
            OPENAI_API_KEY="sk-test-fake-key",
            OPENAI_CHAT_MODEL="gpt-4.1-mini",
            OPENAI_EMBED_MODEL="text-embedding-3-small",
            DOCS_PATH=temp_docs_dir,
            VECTORSTORE_DIR=temp_vs_dir,
            LANGSMITH_TRACING=False,
        )

        # Override create_embeddings and create_chat_llm to return fakes
        fake_embeddings = FakeEmbeddings()
        fake_llm = FakeLLM(response="This is a fake answer from the fake LLM.")

        import app.rag.embeddings as embeddings_module
        import app.rag.chain as chain_module
        from app.main import app as fastapi_app

        original_create_embeddings = embeddings_module.create_embeddings
        original_create_chat_llm = chain_module.create_chat_llm

        embeddings_module.create_embeddings = lambda settings: fake_embeddings
        chain_module.create_chat_llm = lambda settings: fake_llm

        fastapi_app.dependency_overrides[get_settings] = lambda: test_settings

        try:
            client = TestClient(fastapi_app)

            # First, call /ingest to create vector store
            ingest_response = client.post("/ingest", json={"force_rebuild": True})
            assert ingest_response.status_code == 200, (
                f"Ingest failed: {ingest_response.text}"
            )

            # Now call /chat
            chat_response = client.post(
                "/chat",
                json={
                    "session_id": "test-session-123",
                    "message": "What is this document about?",
                    "top_k": 2,
                    "temperature": 0.2,
                }
            )

            # Verify status code
            assert chat_response.status_code == 200, (
                f"Chat must return 200, got {chat_response.status_code}: {chat_response.text}"
            )

            # Verify response structure
            data = chat_response.json()

            # Check required fields
            assert "session_id" in data, "Response must contain session_id"
            assert "answer" in data, "Response must contain answer"
            assert "sources" in data, "Response must contain sources"
            assert "model" in data, "Response must contain model"

            # Verify session_id echoed
            assert data["session_id"] == "test-session-123", (
                "session_id must be echoed back"
            )

            # Verify answer is non-empty string
            assert isinstance(data["answer"], str), "answer must be string"
            assert len(data["answer"]) > 0, "answer must not be empty"

            # Verify sources structure
            assert isinstance(data["sources"], list), "sources must be list"
            assert len(data["sources"]) > 0, "sources must not be empty"

            # Check first source has required fields
            source = data["sources"][0]
            assert "source_id" in source, "Source must have source_id"
            assert "filename" in source, "Source must have filename"
            assert "snippet" in source, "Source must have snippet"

            # Verify model matches config
            assert data["model"] == "gpt-4.1-mini", (
                f"Model must match config, got {data['model']}"
            )

        finally:
            # Restore original functions
            embeddings_module.create_embeddings = original_create_embeddings
            chain_module.create_chat_llm = original_create_chat_llm
            fastapi_app.dependency_overrides.clear()


def test_chat_validates_request():
    """
    Test that /chat validates request parameters.

    Why this test: Ensures Pydantic validation works for:
    - Empty message
    - Invalid top_k range
    - Invalid temperature range
    """
    # Assert: Invalid requests must return 422

    with tempfile.TemporaryDirectory() as temp_docs_dir, \
         tempfile.TemporaryDirectory() as temp_vs_dir:

        test_settings = Settings(
            OPENAI_API_KEY="sk-test-fake-key",
            OPENAI_CHAT_MODEL="gpt-4.1-mini",
            OPENAI_EMBED_MODEL="text-embedding-3-small",
            DOCS_PATH=temp_docs_dir,
            VECTORSTORE_DIR=temp_vs_dir,
            LANGSMITH_TRACING=False,
        )

        from app.main import app as fastapi_app
        fastapi_app.dependency_overrides[get_settings] = lambda: test_settings

        try:
            client = TestClient(fastapi_app)

            # Test empty message (min_length=1)
            response = client.post(
                "/chat",
                json={
                    "message": "",
                    "top_k": 4,
                }
            )
            assert response.status_code == 422, "Empty message must return 422"

            # Test invalid top_k (below minimum)
            response = client.post(
                "/chat",
                json={
                    "message": "test",
                    "top_k": 0,
                }
            )
            assert response.status_code == 422, "top_k=0 must return 422"

            # Test invalid top_k (above maximum)
            response = client.post(
                "/chat",
                json={
                    "message": "test",
                    "top_k": 21,
                }
            )
            assert response.status_code == 422, "top_k=21 must return 422"

            # Test invalid temperature (below minimum)
            response = client.post(
                "/chat",
                json={
                    "message": "test",
                    "temperature": -0.1,
                }
            )
            assert response.status_code == 422, "temperature=-0.1 must return 422"

            # Test invalid temperature (above maximum)
            response = client.post(
                "/chat",
                json={
                    "message": "test",
                    "temperature": 1.1,
                }
            )
            assert response.status_code == 422, "temperature=1.1 must return 422"

        finally:
            fastapi_app.dependency_overrides.clear()


def test_chat_with_query_expansion_enabled():
    """
    Test /chat endpoint with query expansion enabled.

    Why this test: Validates that expansion parameter flows through
    entire pipeline and returns correct response structure.
    """
    # Assert: Response should include expanded_queries field when enabled

    with tempfile.TemporaryDirectory() as temp_docs_dir, \
         tempfile.TemporaryDirectory() as temp_vs_dir:

        # Create test markdown file
        test_file = Path(temp_docs_dir) / "test.md"
        test_file.write_text("# Deployment Guide\n\nTo deploy the application, use the deployment script.")

        test_settings = Settings(
            OPENAI_API_KEY="sk-test-fake-key",
            OPENAI_CHAT_MODEL="gpt-4.1-mini",
            OPENAI_EMBED_MODEL="text-embedding-3-small",
            DOCS_PATH=temp_docs_dir,
            VECTORSTORE_DIR=temp_vs_dir,
            LANGSMITH_TRACING=False,
        )

        # Override with fakes
        fake_embeddings = FakeEmbeddings()
        fake_llm = FakeLLM(response="According to the documentation, use the deployment script.")

        import app.rag.embeddings as embeddings_module
        import app.rag.chain as chain_module
        from app.main import app as fastapi_app

        original_create_embeddings = embeddings_module.create_embeddings
        original_create_chat_llm = chain_module.create_chat_llm

        embeddings_module.create_embeddings = lambda settings: fake_embeddings
        chain_module.create_chat_llm = lambda settings: fake_llm

        fastapi_app.dependency_overrides[get_settings] = lambda: test_settings

        try:
            client = TestClient(fastapi_app)

            # Ingest documents
            ingest_response = client.post("/ingest", json={"force_rebuild": True})
            assert ingest_response.status_code == 200

            # Chat WITH expansion enabled
            chat_response = client.post(
                "/chat",
                json={
                    "message": "How do I deploy?",
                    "top_k": 4,
                    "temperature": 0.2,
                    "enable_query_expansion": True,
                    "num_expansions": 2,
                }
            )

            assert chat_response.status_code == 200
            data = chat_response.json()

            # Verify response structure
            assert "answer" in data
            assert "sources" in data
            assert "expanded_queries" in data

            # Verify expanded_queries is populated
            assert data["expanded_queries"] is not None, "expanded_queries should not be None when expansion enabled"
            assert isinstance(data["expanded_queries"], list), "expanded_queries must be a list"
            assert len(data["expanded_queries"]) >= 1, "Must have at least original query"

            # Verify first query is the original
            assert data["expanded_queries"][0] == "How do I deploy?", "First query should be original"

        finally:
            # Restore original functions
            embeddings_module.create_embeddings = original_create_embeddings
            chain_module.create_chat_llm = original_create_chat_llm
            fastapi_app.dependency_overrides.clear()


def test_chat_expansion_disabled_by_default():
    """
    Test that query expansion is disabled by default (backward compatibility).

    Why this test: Ensures existing clients continue working without
    specifying expansion parameters.
    """
    # Assert: Should work without enable_query_expansion field

    with tempfile.TemporaryDirectory() as temp_docs_dir, \
         tempfile.TemporaryDirectory() as temp_vs_dir:

        test_file = Path(temp_docs_dir) / "test.md"
        test_file.write_text("# Test\n\nTest content.")

        test_settings = Settings(
            OPENAI_API_KEY="sk-test-fake-key",
            OPENAI_CHAT_MODEL="gpt-4.1-mini",
            OPENAI_EMBED_MODEL="text-embedding-3-small",
            DOCS_PATH=temp_docs_dir,
            VECTORSTORE_DIR=temp_vs_dir,
            LANGSMITH_TRACING=False,
        )

        fake_embeddings = FakeEmbeddings()
        fake_llm = FakeLLM(response="Test answer.")

        import app.rag.embeddings as embeddings_module
        import app.rag.chain as chain_module
        from app.main import app as fastapi_app

        original_create_embeddings = embeddings_module.create_embeddings
        original_create_chat_llm = chain_module.create_chat_llm

        embeddings_module.create_embeddings = lambda settings: fake_embeddings
        chain_module.create_chat_llm = lambda settings: fake_llm

        fastapi_app.dependency_overrides[get_settings] = lambda: test_settings

        try:
            client = TestClient(fastapi_app)

            # Ingest
            ingest_response = client.post("/ingest", json={"force_rebuild": True})
            assert ingest_response.status_code == 200

            # Chat WITHOUT expansion fields (backward compatibility)
            chat_response = client.post(
                "/chat",
                json={
                    "message": "Test question",
                    "top_k": 4,
                    # NO enable_query_expansion field
                }
            )

            assert chat_response.status_code == 200
            data = chat_response.json()

            # Should NOT have expanded_queries (or it's None)
            assert data.get("expanded_queries") is None, "expanded_queries should be None when expansion disabled"

        finally:
            embeddings_module.create_embeddings = original_create_embeddings
            chain_module.create_chat_llm = original_create_chat_llm
            fastapi_app.dependency_overrides.clear()


def test_chat_validates_num_expansions_range():
    """
    Test that num_expansions parameter is validated (0-4 range).

    Why this test: Ensures Pydantic validation enforces constraints
    on num_expansions to prevent excessive latency/cost.
    """
    # Assert: Invalid num_expansions should return 422

    with tempfile.TemporaryDirectory() as temp_docs_dir, \
         tempfile.TemporaryDirectory() as temp_vs_dir:

        test_settings = Settings(
            OPENAI_API_KEY="sk-test-fake-key",
            OPENAI_CHAT_MODEL="gpt-4.1-mini",
            OPENAI_EMBED_MODEL="text-embedding-3-small",
            DOCS_PATH=temp_docs_dir,
            VECTORSTORE_DIR=temp_vs_dir,
            LANGSMITH_TRACING=False,
        )

        from app.main import app as fastapi_app
        fastapi_app.dependency_overrides[get_settings] = lambda: test_settings

        try:
            client = TestClient(fastapi_app)

            # Test below minimum (-1)
            response = client.post(
                "/chat",
                json={
                    "message": "Test",
                    "num_expansions": -1,
                }
            )
            assert response.status_code == 422, "num_expansions=-1 must return 422"

            # Test above maximum (5)
            response = client.post(
                "/chat",
                json={
                    "message": "Test",
                    "num_expansions": 5,
                }
            )
            assert response.status_code == 422, "num_expansions=5 must return 422"

            # Test valid boundary (4)
            # Note: This will fail with 409 because vector store doesn't exist,
            # but that's OK - we're just testing parameter validation
            response = client.post(
                "/chat",
                json={
                    "message": "Test",
                    "num_expansions": 4,
                }
            )
            # Should NOT be 422 (parameter validation passed)
            # Will be 409 (vector store not found) which is fine
            assert response.status_code != 422, "num_expansions=4 is valid and should not return 422"

        finally:
            fastapi_app.dependency_overrides.clear()
