import logging
import json
from typing import Optional, Dict, Any
from database.pg_connection import get_db_connection

logger = logging.getLogger(__name__)


def run_migrations():
    """
    Apply all pending SQL migrations from database/migrations/ folder.
    
    Migrations are executed before schema init to ensure proper column structure.
    """
    try:
        from database.run_migrations import run_migrations as _run_migrations
        logger.info("🔄 Running database migrations...")
        _run_migrations()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


def init_postgres_schema():
    """Initialize PostgreSQL database schema with all tables."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Create tenants table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id BIGSERIAL PRIMARY KEY,
                    key TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    system_prompt TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            logger.info("Tenants table created or already exists")
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGSERIAL PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    firstname TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    nickname TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    default_lang TEXT NOT NULL DEFAULT 'en',
                    system_prompt TEXT,
                    default_location TEXT,
                    timezone TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_users_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE
                )
            """)
            logger.info("Users table created or already exists")
            
            # Create chat_sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ended_at TIMESTAMPTZ,
                    processed_for_ltm BOOLEAN NOT NULL DEFAULT FALSE,
                    title TEXT,
                    last_message_at TIMESTAMPTZ,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    CONSTRAINT fk_chat_sessions_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_chat_sessions_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (user_id)
                        ON DELETE CASCADE
                )
            """)
            logger.info("Chat sessions table created or already exists")
            
            # Create chat_messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id BIGSERIAL PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    session_id UUID NOT NULL,
                    user_id BIGINT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_chat_messages_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_chat_messages_session
                        FOREIGN KEY (session_id)
                        REFERENCES chat_sessions (id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_chat_messages_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (user_id)
                        ON DELETE CASCADE
                )
            """)
            logger.info("Chat messages table created or already exists")
            
            # Create long_term_memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    source_session_id UUID,
                    content TEXT NOT NULL,
                    memory_type TEXT CHECK (memory_type IN ('session_summary', 'explicit_fact')),
                    qdrant_point_id UUID,
                    embedded_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_ltm_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_ltm_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (user_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_ltm_session
                        FOREIGN KEY (source_session_id)
                        REFERENCES chat_sessions (id)
                        ON DELETE SET NULL
                )
            """)
            logger.info("Long-term memories table created or already exists")
            
            # Create indexes for long-term memories (from migration 002)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_user_type 
                ON long_term_memories(user_id, memory_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_tenant_type 
                ON long_term_memories(tenant_id, memory_type)
            """)
            
            logger.info("Long-term memories indexes created")
            
            # Create documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT,
                    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'tenant')),
                    source TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_documents_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_documents_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (user_id)
                        ON DELETE SET NULL,
                    CONSTRAINT documents_visibility_user_check
                        CHECK (
                            (visibility = 'private' AND user_id IS NOT NULL)
                            OR
                            (visibility = 'tenant' AND user_id IS NULL)
                        )
                )
            """)
            logger.info("Documents table created or already exists")
            
            # Create document_chunks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    document_id BIGINT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source_title TEXT,
                    chapter_name TEXT,
                    page_start INTEGER,
                    page_end INTEGER,
                    section_level INTEGER,
                    qdrant_point_id UUID,
                    embedded_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_chunks_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_chunks_document
                        FOREIGN KEY (document_id)
                        REFERENCES documents (id)
                        ON DELETE CASCADE,
                    CONSTRAINT uq_document_chunk
                        UNIQUE (document_id, chunk_index)
                )
            """)
            logger.info("Document chunks table created or already exists")
            
            # Create full-text search index on document_chunks.content (Hungarian language)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_content_fts
                ON document_chunks
                USING GIN (to_tsvector('hungarian', content))
            """)
            
            # Create indexes for TOC-based querying (migration 006)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_chapter 
                ON document_chunks(document_id, chapter_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_pages 
                ON document_chunks(document_id, page_start, page_end)
            """)
            
            logger.info("Full-text search index created on document_chunks.content")
            
            # Create user_prompt_cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_prompt_cache (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    cached_prompt TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_prompt_cache_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (user_id)
                        ON DELETE CASCADE
                )
            """)
            
            # Create index for fast user lookup (most recent prompt)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_prompt_cache_user_created 
                ON user_prompt_cache(user_id, created_at DESC)
            """)
            
            logger.info("User prompt cache table created or already exists")
            
            # Create workflow_executions table (observability tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    execution_id UUID PRIMARY KEY,  -- MONITORING: Unique execution identifier
                    request_id TEXT,                -- Legacy field, kept for compatibility
                    tenant_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    session_id UUID NOT NULL,
                    
                    -- Query tracking (debugging: see transformation)
                    query_original TEXT,
                    query_rewritten TEXT,
                    query_intent TEXT,
                    
                    -- Performance metrics
                    intent TEXT,
                    total_duration_ms FLOAT,
                    llm_tokens_total INTEGER DEFAULT 0,
                    llm_cost_usd FLOAT DEFAULT 0.0,
                    tool_calls_count INTEGER DEFAULT 0,
                    chunks_retrieved_count INTEGER DEFAULT 0,
                    
                    -- Cache tracking (prompt caching optimization)
                    llm_tokens_cached INTEGER DEFAULT 0,
                    llm_cache_hit_rate FLOAT DEFAULT 0.0,
                    llm_cost_saved_usd FLOAT DEFAULT 0.0,
                    
                    -- Outcome
                    status TEXT DEFAULT 'in_progress',  -- MONITORING: 'in_progress' | 'completed' | 'failed'
                    success BOOLEAN NOT NULL DEFAULT TRUE,
                    error_message TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,       -- MONITORING: Workflow completion timestamp
                    duration_ms FLOAT,              -- MONITORING: Total execution duration
                    
                    CONSTRAINT fk_workflow_executions_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_workflow_executions_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (user_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_workflow_executions_session
                        FOREIGN KEY (session_id)
                        REFERENCES chat_sessions (id)
                        ON DELETE CASCADE
                )
            """)
            
            # Create node_executions table (node-level tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_executions (
                    id BIGSERIAL PRIMARY KEY,
                    execution_id UUID NOT NULL,     
                    node_name TEXT NOT NULL,        
                    node_index INTEGER NOT NULL,    
                    duration_ms FLOAT NOT NULL,     
                    status TEXT NOT NULL DEFAULT 'success',  
                    error_message TEXT,             
                    metadata JSONB,                 
                    state_before JSONB,             -- State before node execution
                    state_after JSONB,              -- State after node execution
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    
                    CONSTRAINT fk_node_executions_workflow
                        FOREIGN KEY (execution_id)
                        REFERENCES workflow_executions (execution_id)
                        ON DELETE CASCADE
                )
            """)
            
            # Create index for fast execution lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_executions_execution_id 
                ON node_executions(execution_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_executions_node_name 
                ON node_executions(node_name)
            """)
            
            # Create indexes for high-cardinality aggregation queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_executions_tenant_created 
                ON workflow_executions(tenant_id, created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_created 
                ON workflow_executions(user_id, created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_executions_intent 
                ON workflow_executions(intent, created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_executions_success 
                ON workflow_executions(success, created_at DESC)
            """)
            
            logger.info("Workflow executions table created or already exists")
            
            # Create workflow_tracking_config table (runtime-configurable node tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_tracking_config (
                    id BIGSERIAL PRIMARY KEY,
                    config_type TEXT NOT NULL CHECK (config_type IN ('system', 'tenant')),
                    tenant_id BIGINT,
                    
                    node_tracking_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    node_tracking_level TEXT NOT NULL DEFAULT 'OFF' 
                        CHECK (node_tracking_level IN ('OFF', 'METADATA_ONLY', 'FULL_STATE')),
                    
                    tracked_nodes JSONB,
                    override_until TIMESTAMPTZ,
                    
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    
                    CONSTRAINT fk_tracking_config_tenant
                        FOREIGN KEY (tenant_id)
                        REFERENCES tenants (tenant_id)
                        ON DELETE CASCADE,
                    CONSTRAINT uq_config_type_tenant UNIQUE(config_type, tenant_id),
                    CONSTRAINT chk_config_type_tenant CHECK (
                        (config_type = 'system' AND tenant_id IS NULL) OR
                        (config_type = 'tenant' AND tenant_id IS NOT NULL)
                    )
                )
            """)
            
            # Create indexes for tracking config
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_config_tenant 
                ON workflow_tracking_config(tenant_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_config_override 
                ON workflow_tracking_config(override_until) 
                WHERE override_until IS NOT NULL
            """)
            
            logger.info("Workflow tracking config table created or already exists")
            
            conn.commit()
            logger.info("PostgreSQL schema initialization complete")


def seed_database():
    """
    Seed database with initial data from SQL files.
    Runs seed files in order: 00_basic_data.sql, 01_tenant_prompts.sql, 02_user_prompts.sql
    Only runs if database is empty (no tenants exist).
    """
    import os
    import glob
    
    # Check if database already has data
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM tenants")
            result = cursor.fetchone()
            tenant_count = result['count'] if result else 0
            
            if tenant_count > 0:
                logger.info(f"Database already seeded ({tenant_count} tenants exist) - skipping seed")
                return
    
    seed_dir = "/app/data/seed"  # Docker container path
    
    # Check if seed directory exists
    if not os.path.exists(seed_dir):
        logger.warning(f"Seed directory not found: {seed_dir} - skipping seed")
        return
    
    # Get all SQL files sorted by name
    seed_files = sorted(glob.glob(os.path.join(seed_dir, "*.sql")))
    
    if not seed_files:
        logger.warning("No seed SQL files found - skipping seed")
        return
    
    logger.info(f"Found {len(seed_files)} seed files")
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            for seed_file in seed_files:
                filename = os.path.basename(seed_file)
                logger.info(f"  Running seed: {filename}")
                
                try:
                    with open(seed_file, 'r', encoding='utf-8') as f:
                        sql = f.read()
                        cursor.execute(sql)
                        conn.commit()
                        logger.info(f"  ✅ Seed completed: {filename}")
                except Exception as e:
                    logger.error(f"  ❌ Seed failed: {filename} - {e}")
                    conn.rollback()
                    # Continue with next file even if one fails
    
    logger.info("Database seeding complete")


async def seed_documents():
    """
    Seed database with sample documents on first startup.
    
    Uploads test documents with full processing:
    - Extract text content
    - Store in documents table
    - Chunk content
    - Generate embeddings
    - Store in Qdrant vector DB
    
    Only runs if documents table is empty.
    Continues on error (logs and proceeds to next document).
    """
    import os
    from pathlib import Path
    
    # Check if documents already exist
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM documents")
            result = cursor.fetchone()
            doc_count = result['count'] if result else 0
            
            if doc_count > 0:
                logger.info(f"Documents already seeded ({doc_count} documents exist) - skipping document seed")
                return
    
    test_documents_dir = "/test_documents"  # Docker container path
    
    # Check if test_documents directory exists
    if not os.path.exists(test_documents_dir):
        logger.warning(f"Test documents directory not found: {test_documents_dir} - skipping document seed")
        return
    
    # Define documents to upload with their configuration
    documents_to_seed = [
        {
            "filename": "chunk_test_fantasy_törpék_emberek.txt",
            "tenant_id": 1,
            "user_id": 1,
            "visibility": "tenant"
        },
        {
            "filename": "uszkár_kutya.md",
            "tenant_id": 1,
            "user_id": 1,
            "visibility": "private"
        },
        {
            "filename": "chunk_test_fantasy_elfek_orkok.txt",
            "tenant_id": 1,
            "user_id": 2,
            "visibility": "tenant"
        }
    ]
    
    logger.info(f"📄 Seeding {len(documents_to_seed)} test documents...")
    
    # Import workflow components (must be done at runtime to avoid circular imports)
    from services.document_processing_workflow import DocumentProcessingWorkflow
    from services.document_service import DocumentService
    from services.chunking_service import ChunkingService
    from services.embedding_service import EmbeddingService
    from services.qdrant_service import QdrantService
    from database.document_repository import DocumentRepository
    from database.document_chunk_repository import DocumentChunkRepository
    
    # Initialize workflow
    try:
        chunk_repo = DocumentChunkRepository()
        workflow = DocumentProcessingWorkflow(
            doc_service=DocumentService(DocumentRepository()),
            chunking_service=ChunkingService(chunk_repo),
            embedding_service=EmbeddingService(),
            qdrant_service=QdrantService(),
            chunk_repo=chunk_repo
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize DocumentProcessingWorkflow: {e}")
        return
    
    success_count = 0
    
    for doc_config in documents_to_seed:
        filename = doc_config["filename"]
        filepath = os.path.join(test_documents_dir, filename)
        
        if not os.path.exists(filepath):
            logger.warning(f"  ⚠️ Document not found: {filename} - skipping")
            continue
        
        try:
            logger.info(f"  Processing: {filename} (tenant={doc_config['tenant_id']}, user={doc_config['user_id']}, visibility={doc_config['visibility']})")
            
            # Read file content
            with open(filepath, 'rb') as f:
                content_bytes = f.read()
            
            # Determine file type from extension
            file_type = Path(filename).suffix  # e.g., .txt, .md
            
            # Process document through full workflow
            result = await workflow.process_document(
                filename=filename,
                content=content_bytes,
                file_type=file_type,
                tenant_id=doc_config["tenant_id"],
                user_id=doc_config["user_id"],
                visibility=doc_config["visibility"]
            )
            
            if result.get("status") == "success":
                logger.info(
                    f"  ✅ Document processed: {filename} "
                    f"(doc_id={result.get('document_id')}, "
                    f"chunks={result.get('chunk_count')}, "
                    f"embeddings={result.get('embedding_count')})"
                )
                success_count += 1
            else:
                logger.error(f"  ❌ Document processing failed: {filename} - {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            logger.error(f"  ❌ Failed to process document: {filename} - {e}", exc_info=True)
            # Continue with next document
    
    logger.info(f"✅ Document seeding complete: {success_count}/{len(documents_to_seed)} documents processed successfully")


def get_all_tenants():
    """Retrieve all tenants from the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tenant_id, key, name, is_active, created_at, updated_at
                FROM tenants
                ORDER BY name
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def get_active_tenants():
    """Retrieve only active tenants."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tenant_id, key, name, is_active, created_at, updated_at
                FROM tenants
                WHERE is_active = TRUE
                ORDER BY name
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def get_tenant_by_id(tenant_id: int):
    """Retrieve a tenant by ID."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tenant_id, key, name, is_active, system_prompt, created_at, updated_at
                FROM tenants
                WHERE tenant_id = %s
            """, (tenant_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


def update_tenant(tenant_id: int, name: str = None, is_active: bool = None, system_prompt: str = None):
    """
    Update tenant information.
    
    Args:
        tenant_id: Tenant ID to update
        name: New tenant name (optional)
        is_active: New active status (optional)
        system_prompt: New system prompt (optional)
    
    Returns:
        Updated tenant dict or None if not found
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Build dynamic UPDATE query
            update_fields = []
            params = []
            
            if name is not None:
                update_fields.append("name = %s")
                params.append(name)
            
            if is_active is not None:
                update_fields.append("is_active = %s")
                params.append(is_active)
            
            if system_prompt is not None:
                update_fields.append("system_prompt = %s")
                params.append(system_prompt)
            
            if not update_fields:
                # No fields to update, just return current tenant
                return get_tenant_by_id(tenant_id)
            
            # Add updated_at timestamp
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(tenant_id)
            
            query = f"""
                UPDATE tenants
                SET {', '.join(update_fields)}
                WHERE tenant_id = %s
                RETURNING tenant_id, key, name, is_active, system_prompt, created_at, updated_at
            """
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.commit()
            
            return dict(row) if row else None


def get_users_by_tenant(tenant_id: int):
    """Retrieve all users for a specific tenant."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, tenant_id, firstname, lastname, nickname, email, role, is_active, 
                       default_lang, default_location, timezone, created_at
                FROM users
                WHERE tenant_id = %s
                ORDER BY firstname, lastname
            """, (tenant_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def get_all_users_pg():
    """Retrieve all users from PostgreSQL (no tenant filter)."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, tenant_id, firstname, lastname, nickname, email, role, is_active, 
                       default_lang, default_location, timezone, created_at
                FROM users
                ORDER BY tenant_id, firstname, lastname
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def get_user_tenant_id(user_id: int) -> Optional[int]:
    """Get tenant_id for a user (lightweight query for debug/utility purposes)."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tenant_id
                FROM users
                WHERE user_id = %s
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None


def get_user_by_id_pg(user_id: int, tenant_id: int):
    """Retrieve a user by ID from PostgreSQL with tenant isolation."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, tenant_id, firstname, lastname, nickname, email, role, is_active, 
                       default_lang, system_prompt, default_location, timezone, created_at
                FROM users
                WHERE user_id = %s AND tenant_id = %s
            """, (user_id, tenant_id))
            row = cursor.fetchone()
            return dict(row) if row else None


def update_user(
    user_id: int,
    firstname: str = None,
    lastname: str = None,
    nickname: str = None,
    email: str = None,
    role: str = None,
    is_active: bool = None,
    system_prompt: str = None,
    default_lang: str = None
):
    """
    Update user information.
    
    Args:
        user_id: User ID to update
        firstname: New first name (optional)
        lastname: New last name (optional)
        nickname: New nickname (optional)
        email: New email (optional)
        role: New role (optional)
        is_active: New active status (optional)
        system_prompt: New system prompt (optional)
        default_lang: New default language (optional)
    
    Returns:
        Updated user dict or None if not found
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Build dynamic UPDATE query
            update_fields = []
            params = []
            
            if firstname is not None:
                update_fields.append("firstname = %s")
                params.append(firstname)
            
            if lastname is not None:
                update_fields.append("lastname = %s")
                params.append(lastname)
            
            if nickname is not None:
                update_fields.append("nickname = %s")
                params.append(nickname)
            
            if email is not None:
                update_fields.append("email = %s")
                params.append(email)
            
            if role is not None:
                update_fields.append("role = %s")
                params.append(role)
            
            if is_active is not None:
                update_fields.append("is_active = %s")
                params.append(is_active)
            
            if system_prompt is not None:
                update_fields.append("system_prompt = %s")
                params.append(system_prompt)
            
            if default_lang is not None:
                update_fields.append("default_lang = %s")
                params.append(default_lang)
            
            if not update_fields:
                # No fields to update, just return current user
                return get_user_by_id_pg(user_id)
            
            params.append(user_id)
            
            query = f"""
                UPDATE users
                SET {', '.join(update_fields)}
                WHERE user_id = %s
                RETURNING user_id, tenant_id, firstname, lastname, nickname, email, role, is_active, system_prompt, default_lang, created_at
            """
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.commit()
            
            return dict(row) if row else None


def create_session_pg(session_id: str, tenant_id: int, user_id: int, cursor=None):
    """
    Create a new chat session in PostgreSQL.
    
    Args:
        session_id: UUID string for the session
        tenant_id: Tenant ID
        user_id: User ID
        cursor: Optional database cursor. If None, creates own connection and commits.
                If provided, uses the cursor and caller is responsible for commit.
    """
    if cursor is None:
        # Production path: create own connection and commit
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_sessions (id, tenant_id, user_id, created_at)
                    VALUES (%s, %s, %s, NOW())
                """, (session_id, tenant_id, user_id))
                conn.commit()
                logger.info(f"Created session {session_id} for tenant {tenant_id}, user {user_id}")
    else:
        # Test path: use provided cursor, no commit (caller's responsibility)
        cursor.execute("""
            INSERT INTO chat_sessions (id, tenant_id, user_id, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (session_id, tenant_id, user_id))
        logger.info(f"Created session {session_id} for tenant {tenant_id}, user {user_id} (using provided cursor)")


def insert_message_pg(session_id: str, tenant_id: int, user_id: int, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, cursor=None):
    """
    Insert a message into chat_messages table in PostgreSQL.
    
    Also updates session last_message_at and auto-generates title if needed.
    
    Args:
        session_id: Session UUID
        tenant_id: Tenant ID
        user_id: User ID
        role: Message role (user/assistant/system)
        content: Message content
        metadata: Optional dict containing sources, rag_params, workflow_path, actions_taken
        cursor: Optional database cursor. If None, creates own connection and commits.
    """
    if cursor is None:
        # Production path: create own connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_messages (tenant_id, session_id, user_id, role, content, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (tenant_id, session_id, user_id, role, content, json.dumps(metadata) if metadata else None))
                conn.commit()
                logger.info(f"Inserted {role} message for session {session_id}")
                
                # Update session last_message_at
                update_session_last_message_time(session_id)
                
                # Auto-update title if this is a user message
                if role == "user":
                    # Get message count
                    cur.execute("""
                        SELECT COUNT(*) FROM chat_messages 
                        WHERE session_id = %s AND role = 'user'
                    """, (session_id,))
                    result = cur.fetchone()
                    user_message_count = result['count'] if result else 0
                    
                    # Trigger auto-title logic
                    auto_update_session_title(session_id, content, user_message_count)
    else:
        # Test path: use provided cursor
        cursor.execute("""
            INSERT INTO chat_messages (tenant_id, session_id, user_id, role, content, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (tenant_id, session_id, user_id, role, content, json.dumps(metadata) if metadata else None))
        logger.info(f"Inserted {role} message for session {session_id} (using provided cursor)")
        # Note: title update and last_message_at skipped in test mode (would need cursor passing through)


def get_session_messages_pg(session_id: str, limit: int = 20, cursor=None):
    """
    Retrieve the last N messages for a session from PostgreSQL.
    
    Args:
        session_id: Session UUID
        limit: Maximum number of messages to retrieve
        cursor: Optional database cursor. If None, creates own connection.
    """
    if cursor is None:
        # Production path: create own connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT message_id, tenant_id, session_id, user_id, role, content, metadata, created_at
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (session_id, limit))
                rows = cur.fetchall()
                # Return in chronological order, converting datetime to ISO string
                messages = []
                for row in reversed(rows):
                    msg = dict(row)
                    if msg.get('created_at'):
                        msg['created_at'] = msg['created_at'].isoformat()
                    messages.append(msg)
                return messages
    else:
        # Test path: use provided cursor
        cursor.execute("""
            SELECT message_id, tenant_id, session_id, user_id, role, content, metadata, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (session_id, limit))
        rows = cursor.fetchall()
        # Return in chronological order, converting datetime to ISO string
        messages = []
        for row in reversed(rows):
            msg = dict(row)
            if msg.get('created_at'):
                msg['created_at'] = msg['created_at'].isoformat()
            messages.append(msg)
        return messages


def get_last_messages_for_user_pg(user_id: int, tenant_id: int, limit: int = 20):
    """Retrieve the last N messages for a user across all sessions from PostgreSQL (tenant-isolated)."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT message_id, tenant_id, session_id, user_id, role, content, created_at
                FROM chat_messages
                WHERE user_id = %s AND tenant_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, tenant_id, limit))
            rows = cursor.fetchall()
            # Return in chronological order, converting datetime to ISO string
            messages = []
            for row in reversed(rows):
                msg = dict(row)
                if msg.get('created_at'):
                    msg['created_at'] = msg['created_at'].isoformat()
                messages.append(msg)
            return messages


def delete_user_conversation_history_pg(user_id: int):
    """Delete all conversation history (messages and sessions) for a user from PostgreSQL."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # First delete messages (due to foreign key constraint)
            cursor.execute("""
                DELETE FROM chat_messages
                WHERE user_id = %s
            """, (user_id,))
            messages_deleted = cursor.rowcount
            
            # Then delete sessions
            cursor.execute("""
                DELETE FROM chat_sessions
                WHERE user_id = %s
            """, (user_id,))
            sessions_deleted = cursor.rowcount
            
            conn.commit()
            logger.info(f"Deleted all conversation history for user {user_id}: {sessions_deleted} sessions, {messages_deleted} messages")
            
            
            conn.commit()
            logger.info(f"Deleted all conversation history for user {user_id}: {sessions_deleted} sessions, {messages_deleted} messages")
            
            return {
                'sessions_deleted': sessions_deleted,
                'messages_deleted': messages_deleted
            }


def create_long_term_memory(tenant_id: int, user_id: int, content: str, source_session_id: str = None):
    """
    Convenience wrapper for insert_long_term_memory() with default memory_type.
    Defaults to 'explicit_fact' type.
    """
    return insert_long_term_memory(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=source_session_id,
        content=content,
        memory_type='explicit_fact',
        qdrant_point_id=None
    )



    """Retrieve long-term memories for a specific user."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tenant_id, user_id, source_session_id, content, qdrant_point_id, embedded_at, created_at
                FROM long_term_memories
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def update_long_term_memory_embedding(memory_id: int, qdrant_point_id: str):
    """Update a long-term memory with Qdrant point ID after embedding."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE long_term_memories
                SET qdrant_point_id = %s, embedded_at = NOW()
                WHERE id = %s
            """, (qdrant_point_id, memory_id))
            conn.commit()
            logger.info(f"Updated long-term memory {memory_id} with Qdrant point ID")


def delete_long_term_memories_for_user(user_id: int):
    """Delete all long-term memories for a specific user."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM long_term_memories
                WHERE user_id = %s
            """, (user_id,))
            conn.commit()
            logger.info(f"Deleted all long-term memories for user {user_id}")


# ==================== Document Functions ====================

def create_document(tenant_id: int, user_id: int, visibility: str, source: str, title: str, content: str):
    """
    Create a new document.
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID (required for 'private', None for 'tenant')
        visibility: 'private' or 'tenant'
        source: Source of the document (e.g., 'upload', 'api', 'scrape')
        title: Document title
        content: Full document content
    
    Returns:
        Document ID
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO documents (tenant_id, user_id, visibility, source, title, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (tenant_id, user_id, visibility, source, title, content))
            doc_id = cursor.fetchone()['id']
            conn.commit()
            logger.info(f"Created document {doc_id} for tenant {tenant_id}, visibility={visibility}")
            return doc_id


def get_documents_for_user(user_id: int, tenant_id: int):
    """
    Retrieve all documents accessible to a user.
    This includes:
    - Their private documents
    - Tenant-wide documents in their tenant
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tenant_id, user_id, visibility, source, title, created_at
                FROM documents
                WHERE tenant_id = %s 
                  AND (
                      (visibility = 'private' AND user_id = %s)
                      OR
                      (visibility = 'tenant')
                  )
                ORDER BY created_at DESC
            """, (tenant_id, user_id))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def get_documents_by_tenant(tenant_id: int, limit: int = 100):
    """
    Retrieve all documents in a tenant with optional limit.
    Used by knowledge tools for document listing.
    
    Args:
        tenant_id: ID of the tenant
        limit: Maximum number of documents to return
        
    Returns:
        List of document dictionaries with id, title, filename, upload_date, chunk_count
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.id, d.title, d.source as filename, d.created_at as upload_date,
                       COUNT(dc.id) as chunk_count
                FROM documents d
                LEFT JOIN document_chunks dc ON d.id = dc.document_id
                WHERE d.tenant_id = %s
                GROUP BY d.id, d.title, d.source, d.created_at
                ORDER BY d.created_at DESC
                LIMIT %s
            """, (tenant_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def get_document_by_id(document_id: int):
    """Retrieve a document by ID including full content."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tenant_id, user_id, visibility, source, title, content, created_at
                FROM documents
                WHERE id = %s
            """, (document_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


def delete_document(document_id: int):
    """Delete a document and all its chunks (CASCADE)."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM documents
                WHERE id = %s
            """, (document_id,))
            conn.commit()
            logger.info(f"Deleted document {document_id} and its chunks")


# ==================== Document Chunk Functions ====================

def create_document_chunk(
    tenant_id: int,
    document_id: int,
    chunk_index: int,
    start_offset: int,
    end_offset: int,
    content: str,
    source_title: str = None,
    chapter_name: str = None,
    page_start: int = None,
    page_end: int = None
):
    """
    Create a document chunk.
    
    Args:
        tenant_id: Tenant ID
        document_id: Parent document ID
        chunk_index: Sequential index of this chunk
        start_offset: Character offset in original document
        end_offset: Character offset in original document
        content: Chunk text content
        source_title: Original title for source attribution
        chapter_name: Chapter/section name from TOC (renamed from source_section)
        page_start: Starting page number (renamed from source_page_from)
        page_end: Ending page number (renamed from source_page_to)
    
    Returns:
        Chunk ID
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO document_chunks 
                (tenant_id, document_id, chunk_index, start_offset, end_offset, 
                 content, source_title, chapter_name, page_start, page_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (tenant_id, document_id, chunk_index, start_offset, end_offset,
                  content, source_title, chapter_name, page_start, page_end))
            chunk_id = cursor.fetchone()['id']
            conn.commit()
            logger.info(f"Created chunk {chunk_id} for document {document_id}, index={chunk_index}")
            return chunk_id


def get_chunks_for_document(document_id: int):
    """Retrieve all chunks for a document ordered by chunk_index."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tenant_id, document_id, chunk_index, start_offset, end_offset,
                       content, source_title, chapter_name, page_start, page_end,
                       qdrant_point_id, embedded_at, created_at
                FROM document_chunks
                WHERE document_id = %s
                ORDER BY chunk_index
            """, (document_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def update_chunk_embedding(chunk_id: int, qdrant_point_id: str):
    """Update a chunk with Qdrant point ID after embedding."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE document_chunks
                SET qdrant_point_id = %s, embedded_at = NOW()
                WHERE id = %s
            """, (qdrant_point_id, chunk_id))
            conn.commit()
            logger.info(f"Updated chunk {chunk_id} with Qdrant point ID")


def get_chunks_not_embedded(tenant_id: int = None):
    """
    Retrieve chunks that haven't been embedded yet.
    Optionally filter by tenant_id.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            query = """
                SELECT id, tenant_id, document_id, chunk_index, content,
                       source_title, source_section, source_page_from, source_page_to
                FROM document_chunks
                WHERE qdrant_point_id IS NULL
            """
            params = []
            if tenant_id is not None:
                query += " AND tenant_id = %s"
                params.append(tenant_id)
            query += " ORDER BY created_at"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


# ===== SESSION MEMORY FUNCTIONS =====

def get_session_by_id(session_id: str, cursor=None):
    """
    Get session by ID.
    
    Args:
        session_id: Session UUID
        cursor: Optional database cursor. If None, creates own connection.
    """
    if cursor is None:
        # Production path: create own connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, tenant_id, user_id, created_at, 
                           COALESCE(processed_for_ltm, FALSE) as processed_for_ltm
                    FROM chat_sessions
                    WHERE id = %s
                """, (session_id,))
                row = cur.fetchone()
                return dict(row) if row else None
    else:
        # Test path: use provided cursor
        print(f"DEBUG: get_session_by_id called WITH cursor for session {session_id}")
        cursor.execute("""
            SELECT id, tenant_id, user_id, created_at, 
                   COALESCE(processed_for_ltm, FALSE) as processed_for_ltm
            FROM chat_sessions
            WHERE id = %s
        """, (session_id,))
        row = cursor.fetchone()
        print(f"DEBUG: get_session_by_id result: {row}")
        return dict(row) if row else None


def insert_long_term_memory(
    tenant_id: int, 
    user_id: int, 
    session_id: str, 
    content: str, 
    memory_type: str,
    qdrant_point_id: str = None
) -> int:
    """
    Insert long-term memory record.
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        session_id: Source session ID
        content: Full memory content
        memory_type: "session_summary" or "explicit_fact"
        qdrant_point_id: Qdrant point UUID (can be None initially)
    
    Returns:
        Inserted record ID (for Qdrant payload)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO long_term_memories 
                (tenant_id, user_id, source_session_id, content, memory_type, qdrant_point_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
            """, (tenant_id, user_id, session_id, content, memory_type, qdrant_point_id))
            conn.commit()
            result = cursor.fetchone()
            ltm_id = result['id']
            logger.info(f"Inserted long-term memory: id={ltm_id}, type={memory_type}")
            return ltm_id


def get_long_term_memories_by_ids(ltm_ids: list) -> list:
    """
    Batch load long-term memories by IDs.
    
    Used after Qdrant search to retrieve full content for LLM.
    
    Args:
        ltm_ids: List of long_term_memories.id
    
    Returns:
        List of memory records with FULL content
    """
    if not ltm_ids:
        return []
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    id, 
                    tenant_id, 
                    user_id, 
                    source_session_id, 
                    content,
                    memory_type,
                    created_at
                FROM long_term_memories
                WHERE id = ANY(%s)
                ORDER BY created_at DESC
            """, (ltm_ids,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def mark_session_processed_for_ltm(session_id: str):
    """Mark session as processed for long-term memory."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE chat_sessions
                SET processed_for_ltm = TRUE
                WHERE id = %s
            """, (session_id,))
            conn.commit()
            logger.info(f"Marked session {session_id} as processed for LTM")


def get_unprocessed_sessions(older_than_hours: int = 24):
    """Get sessions that haven't been processed for long-term memory."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tenant_id, user_id, created_at
                FROM chat_sessions
                WHERE COALESCE(processed_for_ltm, FALSE) = FALSE
                  AND created_at < NOW() - INTERVAL '%s hours'
                ORDER BY created_at
            """, (older_than_hours,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


# ===== SESSION MANAGEMENT FUNCTIONS (ChatGPT-style) =====

def get_user_sessions(user_id: int, include_deleted: bool = False) -> list[dict]:
    """
    Get all sessions for a user, ordered by most recent activity.
    
    Args:
        user_id: User ID to fetch sessions for
        include_deleted: Whether to include soft-deleted sessions
    
    Returns:
        List of session dictionaries with title, message_count, last_message_at
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            where_clause = "WHERE cs.user_id = %s"
            if not include_deleted:
                where_clause += " AND COALESCE(cs.is_deleted, FALSE) = FALSE"
            
            cursor.execute(f"""
                SELECT 
                    cs.id,
                    cs.title,
                    cs.created_at,
                    cs.last_message_at,
                    cs.is_deleted,
                    cs.processed_for_ltm,
                    COUNT(cm.message_id) as message_count
                FROM chat_sessions cs
                LEFT JOIN chat_messages cm ON cs.id = cm.session_id
                {where_clause}
                GROUP BY cs.id
                ORDER BY cs.last_message_at DESC
            """, (user_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def update_session_title(session_id: str, title: str) -> bool:
    """
    Update session title (user editing).
    
    Args:
        session_id: Session UUID
        title: New title (max 100 chars)
    
    Returns:
        True if updated successfully
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE chat_sessions
                SET title = %s
                WHERE id = %s
            """, (title[:100], session_id))
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Updated session {session_id} title to: {title[:50]}")
            return updated


def soft_delete_session(session_id: str) -> bool:
    """
    Soft delete a session (sets is_deleted = TRUE).
    
    Args:
        session_id: Session UUID
    
    Returns:
        True if deleted successfully
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE chat_sessions
                SET is_deleted = TRUE
                WHERE id = %s
            """, (session_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Soft deleted session: {session_id}")
            return deleted


def update_session_last_message_time(session_id: str) -> None:
    """
    Update last_message_at timestamp when new message is added.
    
    Args:
        session_id: Session UUID
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE chat_sessions
                SET last_message_at = NOW()
                WHERE id = %s
            """, (session_id,))
            conn.commit()


def auto_update_session_title(session_id: str, message_content: str, message_count: int) -> None:
    """
    Auto-generate session title based on hybrid logic.
    
    Logic:
    - Message 1: If len >= 20 or contains '?', use as title
    - Message 3: If still NULL, find first meaningful message
    
    Args:
        session_id: Session UUID
        message_content: Current user message
        message_count: Total messages in session
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Get current title
            cursor.execute("SELECT title FROM chat_sessions WHERE id = %s", (session_id,))
            result = cursor.fetchone()
            if not result:
                return
            
            current_title = result['title']
            
            # Message 1 logic
            if message_count == 1:
                if len(message_content) >= 20 or '?' in message_content:
                    new_title = message_content[:50] + ("..." if len(message_content) > 50 else "")
                    cursor.execute("""
                        UPDATE chat_sessions SET title = %s WHERE id = %s
                    """, (new_title, session_id))
                    conn.commit()
                    logger.info(f"Auto-set title (msg 1): {new_title}")
                return
            
            # Message 3 logic (if still NULL)
            if message_count == 3 and current_title is None:
                # Find first meaningful message
                cursor.execute("""
                    SELECT content FROM chat_messages
                    WHERE session_id = %s AND role = 'user'
                    ORDER BY created_at
                    LIMIT 3
                """, (session_id,))
                messages = cursor.fetchall()
                
                for msg in messages:
                    content = msg['content']
                    if len(content) >= 30 or '?' in content:
                        new_title = content[:50] + ("..." if len(content) > 50 else "")
                        cursor.execute("""
                            UPDATE chat_sessions SET title = %s WHERE id = %s
                        """, (new_title, session_id))
                        conn.commit()
                        logger.info(f"Auto-set title (msg 3): {new_title}")
                        break


# ===== USER PROMPT CACHE FUNCTIONS =====

def get_latest_cached_prompt(user_id: int) -> str | None:
    """
    Get the most recent cached system prompt for a user.
    
    Args:
        user_id: User ID to fetch cached prompt for
    
    Returns:
        Cached prompt text or None if no cache exists
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT cached_prompt
                FROM user_prompt_cache
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[CACHE] Retrieved cached prompt for user_id={user_id}")
                return result['cached_prompt']
            else:
                logger.info(f"[CACHE] No cached prompt found for user_id={user_id}")
                return None


def save_cached_prompt(user_id: int, cached_prompt: str) -> int:
    """
    Save a new cached system prompt for a user.
    
    Args:
        user_id: User ID to save prompt for
        cached_prompt: Optimized system prompt text
    
    Returns:
        ID of inserted cache record
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_prompt_cache (user_id, cached_prompt, created_at)
                VALUES (%s, %s, NOW())
                RETURNING id
            """, (user_id, cached_prompt))
            
            result = cursor.fetchone()
            conn.commit()
            
            cache_id = result['id']
            logger.info(f"[CACHE] Saved cached prompt: user_id={user_id}, cache_id={cache_id}")
            return cache_id


def get_prompt_cache_history(user_id: int, limit: int = 10) -> list[dict]:
    """
    Get prompt cache history for a user (for debugging/rollback).
    
    Args:
        user_id: User ID to fetch history for
        limit: Maximum number of records to return
    
    Returns:
        List of cached prompts with metadata
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, cached_prompt, created_at
                FROM user_prompt_cache
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


# ==================== Long-Term Memory Functions ====================

def create_long_term_memory(tenant_id: int, user_id: int, content: str, source_session_id: str = None):
    """Create a new long-term memory entry."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO long_term_memories (tenant_id, user_id, source_session_id, content, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING id
            """, (tenant_id, user_id, source_session_id, content))
            result = cursor.fetchone()
            conn.commit()
            memory_id = result['id'] if result else None
            logger.info(f"Created long-term memory {memory_id} for user {user_id}")
            return memory_id


def get_long_term_memories_for_user(user_id: int, limit: int = 50):
    """Retrieve long-term memories for a specific user."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tenant_id, user_id, source_session_id, content, memory_type, 
                       qdrant_point_id, embedded_at, created_at
                FROM long_term_memories
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
