"""
Pytest configuration and shared fixtures.
Knowledge Router PROD - Test Infrastructure

Fixtures:
- db_session: PostgreSQL connection
- qdrant_client: Qdrant client
- test_client: FastAPI TestClient
- mock_openai: Mock OpenAI API responses
- test_data: Seeded test data (tenant_id=1, user_id=1)
"""

import pytest
import os
import logging
from typing import Generator, Dict, Any
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import psycopg2
from psycopg2.extras import RealDictCursor
from qdrant_client import QdrantClient

# ============================================================================
# SUPPRESS HTTPCORE LOGGING (module level - runs before any tests)
# ============================================================================
# Suppress httpcore/httpx debug logging to prevent 'I/O operation on closed file'
# errors during Python shutdown. These loggers emit debug messages during HTTP
# operations, and if the logging system is shutting down, these writes fail.
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Mark all tests to use asyncio
pytest_plugins = ('pytest_asyncio',)


# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set testing environment variables."""
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    # CRITICAL: If --run-openai flag present, ensure OPENAI_API_KEY available
    # This allows workflow initialization during test_client creation
    if not os.getenv("OPENAI_API_KEY"):
        # Check if we're in OpenAI test mode (marker detected by pytest)
        # If so, warn but don't fail - individual tests will fail gracefully
        import sys
        if "--run-openai" in sys.argv:
            print("⚠️  WARNING: --run-openai flag set but OPENAI_API_KEY not in environment")
            print("    Set OPENAI_API_KEY env variable before running OpenAI tests")
    
    yield
    os.environ.pop("TESTING", None)


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def db_connection() -> Generator:
    """PostgreSQL connection (session-scoped) with AUTOCOMMIT for test visibility."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        database=os.getenv("POSTGRES_DB", "k_r_")
    )
    conn.autocommit = True  # Enable autocommit for integration tests
    yield conn
    conn.close()


@pytest.fixture
def db_session(db_connection) -> Generator:
    """
    Database cursor using the same connection pool as application code.
    Uses db_connection fixture to ensure isolation but allows cross-connection visibility.
    """
    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()
    # Note: db_connection cleanup handles rollback/commit


# ============================================================================
# QDRANT FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def qdrant_client() -> QdrantClient:
    """Qdrant client (session-scoped)."""
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "qdrant"),
        port=int(os.getenv("QDRANT_PORT", 6333))
    )


@pytest.fixture
def clean_qdrant_collection(qdrant_client):
    """
    Clean test collection in Qdrant before test.
    Creates 'test_collection' for isolated testing.
    """
    collection_name = "test_collection"
    
    # Delete if exists
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass
    
    # Create fresh
    from qdrant_client.models import Distance, VectorParams
    from services.config_service import get_config_service
    
    config = get_config_service()
    vector_dims = config.get_embedding_dimensions()
    
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_dims, distance=Distance.COSINE)
    )
    
    yield collection_name
    
    # Cleanup
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass


# ============================================================================
# FASTAPI TEST CLIENT
# ============================================================================

@pytest.fixture
def test_client() -> TestClient:
    """
    FastAPI TestClient for API endpoint testing.
    
    CRITICAL: TestClient in pytest does NOT trigger app lifespan events!
    We must manually call startup logic before creating the client.
    """
    import sys
    from main import app
    from api.dependencies import init_workflows
    
    # MANUALLY trigger startup logic (TestClient won't do it)
    sys.stderr.write("🔧 [CONFTEST] Manually triggering app startup for test\n")
    sys.stderr.flush()
    init_workflows()
    sys.stderr.write("   [CONFTEST] Workflow initialized\n")
    sys.stderr.flush()
    
    client = TestClient(app)
    return client


# ============================================================================
# OPENAI MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_openai_chat_completion():
    """
    Mock OpenAI ChatCompletion.create() for tests WITHOUT @pytest.mark.openai.
    Returns deterministic response.
    """
    mock_response = {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a mocked OpenAI response for testing."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
    
    with patch("openai.ChatCompletion.create", return_value=mock_response) as mock:
        yield mock


@pytest.fixture
def mock_openai_embedding():
    """
    Mock OpenAI Embedding.create() for tests WITHOUT @pytest.mark.openai.
    Returns deterministic 3072-dim vector (text-embedding-3-large).
    """
    import numpy as np
    
    mock_response = {
        "object": "list",
        "data": [{
            "object": "embedding",
            "embedding": np.random.rand(3072).tolist(),  # text-embedding-3-large dimensions
            "index": 0
        }],
        "model": "text-embedding-3-large",
        "usage": {
            "prompt_tokens": 5,
            "total_tokens": 5
        }
    }
    
    with patch("openai.Embedding.create", return_value=mock_response) as mock:
        yield mock


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def test_tenant_user(db_session) -> Dict[str, int]:
    """
    Returns seeded test data IDs.
    Assumes seed data loaded: tenant_id=1, user_id=1 (Alice).
    """
    # Verify seed data exists
    db_session.execute("SELECT tenant_id FROM tenants WHERE tenant_id = 1")
    tenant = db_session.fetchone()
    
    db_session.execute("SELECT user_id FROM users WHERE user_id = 1")
    user = db_session.fetchone()
    
    assert tenant, "Seed data missing: tenant_id=1 not found"
    assert user, "Seed data missing: user_id=1 not found"
    
    return {
        "tenant_id": 1,
        "user_id": 1,
        "username": "alice"
    }


@pytest.fixture
def test_session(db_session, test_tenant_user) -> Dict[str, Any]:
    """
    Create a test chat session using create_session_pg with provided cursor.
    This ensures the session is created in the same transaction/connection as tests.
    """
    import uuid
    from database.pg_init import create_session_pg
    
    session_id = str(uuid.uuid4())
    
    # Use create_session_pg with cursor parameter to stay in same transaction
    create_session_pg(
        session_id=session_id,
        tenant_id=test_tenant_user["tenant_id"],
        user_id=test_tenant_user["user_id"],
        cursor=db_session  # Pass test cursor to avoid new connection
    )
    
    return {
        "session_id": session_id,
        **test_tenant_user
    }
    print(f"DEBUG FIXTURE: tenant_id={test_tenant_user['tenant_id']}, user_id={test_tenant_user['user_id']}", file=sys.stderr, flush=True)
    print(f"DEBUG FIXTURE: db_session cursor: {type(db_session)}", file=sys.stderr, flush=True)
    
    # Use create_session_pg with cursor parameter to stay in same transaction
    create_session_pg(
        session_id=session_id,
        tenant_id=test_tenant_user["tenant_id"],
        user_id=test_tenant_user["user_id"],
        cursor=db_session  # Pass test cursor to avoid new connection
    )
    
    print(f"DEBUG FIXTURE: create_session_pg returned successfully", file=sys.stderr, flush=True)
    
    return {
        "session_id": session_id,
        **test_tenant_user
    }


@pytest.fixture
def test_document(db_session, test_tenant_user) -> Dict[str, Any]:
    """
    Create a test document with chunks.
    Returns document_id and chunk_ids.
    """
    from database.pg_init import create_document, create_document_chunk
    
    doc_id = create_document(
        tenant_id=test_tenant_user["tenant_id"],
        user_id=test_tenant_user["user_id"],
        visibility="private",
        source="upload",
        title="Test Document",
        content="This is a test document for pytest. It contains important information about testing."
    )
    
@pytest.fixture
def test_document(db_session, test_tenant_user) -> Dict[str, Any]:
    """
    Create a test document with chunks AND Qdrant indexing.
    
    This fixture:
    1. Creates document in PostgreSQL
    2. Creates chunks
    3. Embeds and indexes chunks in Qdrant (if OPENAI_API_KEY available)
    
    Uses the PRODUCTION Qdrant collection (not test_collection) so that
    the UnifiedChatWorkflow can find the documents during RAG tests.
    
    Returns document_id and chunk_ids for test usage.
    """
    from database.pg_init import create_document, create_document_chunk
    import uuid
    import os
    
    test_content = """
    This is a comprehensive test document about artificial intelligence and machine learning.
    
    Machine learning is a subset of AI that enables computers to learn from data.
    Deep learning uses neural networks with multiple layers to process complex patterns.
    
    Key ML concepts include:
    - Supervised learning: training with labeled data
    - Unsupervised learning: finding patterns in unlabeled data
    - Reinforcement learning: learning through trial and error
    
    Natural language processing (NLP) is a branch of AI focused on text understanding.
    """
    
    doc_id = create_document(
        tenant_id=test_tenant_user["tenant_id"],
        user_id=test_tenant_user["user_id"],
        visibility="private",
        source="test_upload",
        title="Test AI Document",
        content=test_content
    )
    
    # Create chunks from the content
    chunks_data = [
        {
            "content": "This is a comprehensive test document about artificial intelligence and machine learning. Machine learning is a subset of AI that enables computers to learn from data.",
            "start": 0,
            "end": 160
        },
        {
            "content": "Deep learning uses neural networks with multiple layers to process complex patterns. Key ML concepts include supervised learning, unsupervised learning, and reinforcement learning.",
            "start": 160,
            "end": 340
        },
        {
            "content": "Natural language processing (NLP) is a branch of AI focused on text understanding.",
            "start": 340,
            "end": 422
        }
    ]
    
    chunk_ids = []
    qdrant_indexed = False
    
    for idx, chunk_data in enumerate(chunks_data):
        chunk_id = create_document_chunk(
            tenant_id=test_tenant_user["tenant_id"],
            document_id=doc_id,
            chunk_index=idx,
            start_offset=chunk_data["start"],
            end_offset=chunk_data["end"],
            content=chunk_data["content"],
            source_title="Test AI Document",
            chapter_name=f"Section {idx + 1}"
        )
        chunk_ids.append(chunk_id)
    
    # Try to embed and index in Qdrant (only if OPENAI_API_KEY available)
    if os.getenv("OPENAI_API_KEY"):
        print(f"\n🔍 [FIXTURE] OPENAI_API_KEY found, attempting Qdrant indexing...")
        try:
            from services.embedding_service import EmbeddingService
            from services.qdrant_service import QdrantService
            from database.pg_init import update_chunk_embedding
            import logging
            
            logger = logging.getLogger(__name__)
            print(f"🔍 [FIXTURE] Services imported successfully")
            
            embedding_service = EmbeddingService()
            qdrant_service = QdrantService()
            tenant_id = test_tenant_user["tenant_id"]
            
            print(f"🔍 [FIXTURE] Services initialized, starting embedding of {len(chunks_data)} chunks...")
            
            # Prepare chunks for batch upsert (QdrantService expects this format)
            chunks_for_qdrant = []
            for idx, chunk_data in enumerate(chunks_data):
                chunk_id = chunk_ids[idx]
                
                # Generate embedding
                embedding = embedding_service.generate_embedding(chunk_data["content"])
                print(f"🔍 [FIXTURE] Chunk {idx}: embedding generated ({len(embedding)} dims)")
                
                chunks_for_qdrant.append({
                    "chunk_id": chunk_id,
                    "embedding": embedding,
                    "tenant_id": tenant_id,
                    "document_id": doc_id,
                    "user_id": test_tenant_user["user_id"],
                    "visibility": "private",
                    "content": chunk_data["content"]
                })
            
            # Batch upsert to Qdrant (returns [{"chunk_id": int, "qdrant_point_id": str}, ...])
            # Use DEFAULT collection (not test_collection) so workflow can find documents
            print(f"🔍 [FIXTURE] Upserting {len(chunks_for_qdrant)} chunks to Qdrant default collection...")
            results = qdrant_service.upsert_document_chunks(chunks_for_qdrant)  # Use default collection
            print(f"🔍 [FIXTURE] Qdrant upsert returned {len(results)} results")
            
            # Update PostgreSQL chunks with Qdrant point IDs
            for result in results:
                update_chunk_embedding(result["chunk_id"], result["qdrant_point_id"])
                print(f"🔍 [FIXTURE] Chunk {result['chunk_id']}: DB updated with point_id {result['qdrant_point_id']}")
            
            qdrant_indexed = True
            print(f"✅ [FIXTURE] Test document SUCCESSFULLY indexed: doc_id={doc_id}, chunks={len(chunk_ids)}")
            logger.info(f"✅ Test document indexed in Qdrant: doc_id={doc_id}, chunks={len(chunk_ids)}")
            
        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            
            print(f"❌ [FIXTURE] Exception during indexing: {e}")
            print(f"   Traceback:\n{traceback.format_exc()}")
            logger.error(f"⚠️ Could not index test document in Qdrant: {e}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            logger.warning("   RAG tests will skip")
    else:
        print(f"⚠️ [FIXTURE] OPENAI_API_KEY not set - skipping Qdrant indexing")
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("⚠️ OPENAI_API_KEY not set - test document will not be indexed in Qdrant")
    
    document = {
        "document_id": doc_id,
        "chunk_ids": chunk_ids,
        "qdrant_indexed": qdrant_indexed,
        **test_tenant_user
    }
    
    yield document
    
    # Cleanup: delete document (CASCADE deletes chunks)
    db_session.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    db_session.connection.commit()
    
    # Cleanup Qdrant points (if they were created)
    if qdrant_indexed:
        try:
            from services.qdrant_service import QdrantService
            qdrant_service = QdrantService()
            
            # Get point IDs before deletion
            db_session.execute("""
                SELECT qdrant_point_id FROM document_chunks
                WHERE document_id = %s AND qdrant_point_id IS NOT NULL
            """, (doc_id,))
            point_ids = [row['qdrant_point_id'] for row in db_session.fetchall()]
            
            # Delete from Qdrant (note: no delete_point method, just leave orphaned for now)
            # TODO: Implement proper Qdrant cleanup or collection reset
            
            print(f"✅ [FIXTURE] Test document cleanup: {len(point_ids)} Qdrant points left orphaned")
        except Exception as e:
            print(f"⚠️ [FIXTURE] Qdrant cleanup query failed: {e}")


# ============================================================================
# MARKER HOOKS
# ============================================================================

def pytest_configure(config):
    """Register custom markers and handle OpenAI test confirmation."""
    config.addinivalue_line(
        "markers", "openai: mark test as requiring real OpenAI API calls (cost!)"
    )
    
    # MINDIG interaktív prompt OpenAI tesztekhez
    import sys
    
    print("\n" + "="*60)
    print("🧪 PYTEST INDÍTÁS - OpenAI teszt opció")
    print("="*60)
    print("A Knowledge Router pytest suite tartalmaz OpenAI API teszteket.")
    print("Ezek valódi API hívásokat végeznek és token költséggel járnak!")
    print()
    
    # Check environment variable first (for CI/CD and non-interactive runs)
    run_openai_env = os.getenv("RUN_OPENAI_TESTS", "").upper()
    
    if run_openai_env in ['1', 'TRUE', 'YES', 'Y', 'I', 'IGEN']:
        print("\n⚠️  OpenAI tesztek futtatása ENGEDÉLYEZVE (RUN_OPENAI_TESTS env)")
        print("   Költségkockázat elfogadva\n")
        config.option.run_openai = True
    elif run_openai_env in ['0', 'FALSE', 'NO', 'N']:
        print("\n✅ OpenAI tesztek kihagyása (RUN_OPENAI_TESTS env)")
        print("   Csak a mock/offline tesztek futnak\n")
        config.option.run_openai = False
    else:
        # Interactive mode only if no env var set
        try:
            # MINDIG kérdés, minden futtatásnál (ha nincs env var)
            response = input("Futtassuk az OpenAI teszteket is? (I/N): ").strip().upper()
            if response not in ['I', 'Y', 'YES', 'IGEN']:
                print("\n✅ OpenAI tesztek kihagyása")
                print("   Csak a mock/offline tesztek futnak\n")
                # Biztosítjuk, hogy ne fusson OpenAI teszt
                config.option.run_openai = False
            else:
                print("\n⚠️  OpenAI tesztek futtatása ENGEDÉLYEZVE")
                print("   Költségkockázat elfogadva\n")
                # Dinamikusan beállítjuk az OpenAI teszt futtatását
                config.option.run_openai = True
        except (KeyboardInterrupt, EOFError):
            print("\n\n❌ Megszakítva - pytest leállítása")
            sys.exit(0)


def pytest_collection_modifyitems(config, items):
    """
    Skip @pytest.mark.openai tests by default.
    Run with: pytest --run-openai
    """
    run_openai = config.getoption("--run-openai", default=False)
    
    skip_openai = pytest.mark.skip(reason="OpenAI test skipped (use --run-openai to enable)")
    
    for item in items:
        if "openai" in item.keywords and not run_openai:
            item.add_marker(skip_openai)


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--run-openai",
        action="store_true",
        default=False,
        help="Run tests that call real OpenAI API (incurs cost)"
    )
