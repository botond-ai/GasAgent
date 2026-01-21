"""
Memory Consolidation Service - STM → LTM Extraction

Extracts key facts and preferences from session-level short-term memory (STM)
and stores them as persistent long-term memories (LTM) in PostgreSQL.

Architecture (TASK-014.2):
- STM = Session-scoped chat messages (working memory)
- LTM = User-level persistent facts (cross-session knowledge)
- Consolidation triggers: session idle, session switch, new session button

Strategy (Opció 3 - CLEAN SLATE):
- After consolidation: STM cache cleared (not needed, auto-expires)
- Session reopened: LTM provides context, STM starts fresh
- No duplication: LTM = past knowledge, STM = current session only
"""

import logging
import json
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from services.config_service import get_config_service
from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService
from services.protocols import IEmbeddingService, IQdrantService
from services.qdrant_service import QdrantService
from database.pg_init import (
    get_session_messages_pg,
    insert_long_term_memory,
    get_db_connection
)

logger = logging.getLogger(__name__)


class MemoryConsolidationService:
    """Service for extracting key facts from STM and storing as LTM."""

    def __init__(
        self,
        openai_api_key: str,
        embedding_service: Optional[IEmbeddingService] = None,
        qdrant_service: Optional[IQdrantService] = None
    ):
        """
        Initialize consolidation service with dependency injection.

        Args:
            openai_api_key: OpenAI API key for LLM-based extraction
            embedding_service: Optional embedding service (default: creates new)
            qdrant_service: Optional Qdrant service (default: creates new)
        """
        from core.dependencies import get_embedding_service, get_qdrant_service
        
        config = get_config_service()

        # Use lightweight model for memory consolidation (compression task)
        self.llm = ChatOpenAI(
            model=config.get_light_model(),
            temperature=config.get_light_router_temperature(),  # Deterministic for factual extraction
            max_tokens=config.get_light_router_max_tokens(),
            api_key=openai_api_key
        )

        # Services for embedding and storage (with DI)
        self.embedding_service = embedding_service or get_embedding_service()
        self.qdrant_service = qdrant_service or get_qdrant_service()

        logger.info(
            f"MemoryConsolidationService initialized with lightweight model: {config.get_light_model()}"
        )

    async def consolidate_session(
        self,
        session_id: str,
        user_id: int,
        tenant_id: int
    ) -> Dict[str, Any]:
        """
        Consolidate session STM → LTM.

        Steps:
        1. Fetch session messages (STM source)
        2. Extract key facts using LLM
        3. Store facts in long_term_memories table
        4. Mark session as processed_for_ltm

        Args:
            session_id: Session to consolidate
            user_id: User ID (for LTM ownership)
            tenant_id: Tenant ID (for multi-tenancy)

        Returns:
            {
                "status": "success" | "skipped" | "error",
                "facts_extracted": int,
                "message": str
            }
        """
        try:
            logger.info(f"🔄 Starting consolidation: session={session_id}, user={user_id}")

            # === STEP 1: Check if already consolidated ===
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT processed_for_ltm FROM chat_sessions
                        WHERE id = %s AND user_id = %s AND tenant_id = %s
                    """, (session_id, user_id, tenant_id))
                    result = cursor.fetchone()

                    if not result:
                        logger.warning(f"⚠️ Session not found: {session_id}")
                        return {
                            "status": "error",
                            "facts_extracted": 0,
                            "message": "Session not found"
                        }

                    if result['processed_for_ltm']:
                        logger.info(f"✅ Session already consolidated: {session_id}")
                        return {
                            "status": "skipped",
                            "facts_extracted": 0,
                            "message": "Session already consolidated"
                        }

            # === STEP 2: Fetch session messages (STM source) ===
            messages = get_session_messages_pg(session_id, limit=100)  # Get all messages

            if len(messages) < 3:
                logger.info(f"⚠️ Session too short ({len(messages)} messages), skipping consolidation")
                return {
                    "status": "skipped",
                    "facts_extracted": 0,
                    "message": f"Session too short ({len(messages)} messages)"
                }

            logger.info(f"📚 Loaded {len(messages)} messages from session {session_id}")

            # === STEP 3: Extract key facts using LLM ===
            facts = await self._extract_facts_from_conversation(messages)

            if not facts:
                logger.info(f"⚠️ No facts extracted from session {session_id}")
                # Still mark as processed to avoid re-processing
                self._mark_session_processed(session_id, user_id, tenant_id)
                return {
                    "status": "success",
                    "facts_extracted": 0,
                    "message": "No significant facts found"
                }

            # === Store facts in LTM with duplicate detection ===
            stored_count = 0
            skipped_count = 0

            for fact in facts:
                fact_content = fact['content']

                # Generate embedding for duplicate detection
                fact_embedding = self.embedding_service.generate_embedding(fact_content)

                # Check for duplicates in Qdrant (same user, high similarity)
                similar_memories = self.qdrant_service.search_long_term_memories(
                    query_vector=fact_embedding,
                    user_id=user_id,
                    limit=1,
                    score_threshold=0.9  # High threshold = very similar
                )

                if similar_memories:
                    logger.info(f"⚠️ Duplicate detected (similarity={similar_memories[0]['score']:.3f}): '{fact_content[:50]}...'")
                    skipped_count += 1
                    continue

                # Store in PostgreSQL
                ltm_id = insert_long_term_memory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                    content=fact_content,
                    memory_type='explicit_fact',
                    qdrant_point_id=None
                )

                if not ltm_id:
                    logger.error(f"❌ Failed to create LTM in PostgreSQL for: '{fact_content[:50]}...'")
                    continue

                # Store in Qdrant
                try:
                    qdrant_point_id = self.qdrant_service.upsert_long_term_memory(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        session_id=session_id,
                        memory_type=fact.get('type', 'fact'),
                        ltm_id=ltm_id,
                        content_full=fact_content,
                        embedding_vector=fact_embedding
                    )

                    # Update PostgreSQL with Qdrant point ID
                    with get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                UPDATE long_term_memories
                                SET qdrant_point_id = %s, embedded_at = NOW()
                                WHERE id = %s
                            """, (qdrant_point_id, ltm_id))
                            conn.commit()

                    logger.info(f"💾 Stored LTM: ltm_id={ltm_id}, qdrant_id={qdrant_point_id}")
                    stored_count += 1

                except Exception as e:
                    logger.error(f"❌ Failed to store in Qdrant: {e}")
                    # PostgreSQL still has it, Qdrant can be retried later

            logger.info(f"💾 LTM consolidation: {stored_count} stored, {skipped_count} skipped (duplicates)")

            # === STEP 5: Mark session as consolidated ===
            self._mark_session_processed(session_id, user_id, tenant_id)

            return {
                "status": "success",
                "facts_extracted": len(facts),
                "facts_stored": stored_count,
                "facts_skipped": skipped_count,
                "message": f"Consolidated {stored_count} new facts ({skipped_count} duplicates skipped)"
            }

        except Exception as e:
            logger.error(f"❌ Consolidation failed for session {session_id}: {e}", exc_info=True)
            return {
                "status": "error",
                "facts_extracted": 0,
                "message": f"Consolidation error: {str(e)}"
            }

    async def _extract_facts_from_conversation(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Use LLM to extract key facts from conversation history.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            List of fact dicts: [{"type": "fact"|"preference", "content": "..."}]
        """
        # Build conversation text
        conversation = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in messages
        ])

        # Extraction prompt
        system_prompt = """Elemezd ezt a beszélgetést és gyűjts ki 3-5 kulcsfontosságú tényt vagy preferenciát a felhasználóról.

CSAK konkrét, releváns információkat adj vissza:
- Tények: konkrét adatok (pl. "A felhasználó backend fejlesztő", "Python nyelvet használ")
- Preferenciák: ismétlődő mintázatok (pl. "Rövid válaszokat kedvel", "Magyar nyelven kommunikál")

KERÜLD:
- Triviális megjegyzéseket ("A user kérdezett valamit")
- Beszélgetés-specifikus kontextust ("A user feltöltött egy dokumentumot")
- Technikai részleteket amelyek nem általános tudás

Válasz formátuma (JSON array):
[
  {"type": "fact", "content": "konkrét tény itt"},
  {"type": "preference", "content": "preferencia itt"}
]

Ha nincs releváns információ, adj vissza üres array-t: []"""

        messages_for_llm = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=conversation)
        ]

        try:
            logger.info("🤖 Calling LLM for fact extraction...")
            response = await self.llm.ainvoke(messages_for_llm)
            response_text = response.content.strip()

            logger.debug(f"📝 LLM response: {response_text}")

            # Parse JSON response
            # Handle markdown code blocks if present
            if response_text.startswith("```"):
                # Extract JSON from markdown code block
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            facts = json.loads(response_text)

            if not isinstance(facts, list):
                logger.warning(f"⚠️ LLM returned non-list response: {response_text}")
                return []

            # Validate fact structure
            valid_facts = []
            for fact in facts:
                if isinstance(fact, dict) and 'content' in fact and fact['content'].strip():
                    valid_facts.append(fact)
                else:
                    logger.warning(f"⚠️ Invalid fact structure: {fact}")

            return valid_facts

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            return []

        except Exception as e:
            logger.error(f"❌ LLM fact extraction failed: {e}", exc_info=True)
            return []

    def _mark_session_processed(self, session_id: str, user_id: int, tenant_id: int):
        """
        Mark session as consolidated in database.

        Args:
            session_id: Session ID
            user_id: User ID (for security check)
            tenant_id: Tenant ID (for multi-tenancy)
        """
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE chat_sessions
                    SET processed_for_ltm = TRUE
                    WHERE id = %s AND user_id = %s AND tenant_id = %s
                """, (session_id, user_id, tenant_id))
                conn.commit()

                logger.info(f"✅ Marked session {session_id} as processed_for_ltm")


# === GLOBAL INSTANCE ===

_consolidation_service: Optional[MemoryConsolidationService] = None


def get_consolidation_service() -> MemoryConsolidationService:
    """
    Get global consolidation service instance (lazy initialization).

    Returns:
        MemoryConsolidationService instance
    """
    global _consolidation_service

    if _consolidation_service is None:
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        _consolidation_service = MemoryConsolidationService(api_key)

    return _consolidation_service