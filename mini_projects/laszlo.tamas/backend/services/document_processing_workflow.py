"""
Document Processing Workflow (LangGraph)

Full automated pipeline: upload → extract → chunk → embed → Qdrant

WHY LangGraph:
- Eliminates manual 3-step process (upload → chunk → embed)
- Error handling at each step with state tracking
- Automatic retry logic
- Clear visibility into processing stages
- Easier debugging (state inspection)

Workflow:
START → validate_file → extract_content → store_document 
      → chunk_document → generate_embeddings → upsert_to_qdrant 
      → verify_completion → END
"""

import logging
from typing import TypedDict, List, Optional, Dict, Any, Literal, Tuple
from langgraph.graph import StateGraph, END
from io import BytesIO
import time
import asyncio

from services.document_service import DocumentService
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService
from services.config_service import ConfigService
from database.document_chunk_repository import DocumentChunkRepository
from services.websocket_manager import websocket_manager
from services.protocols import (
    IDocumentService,
    IChunkingService,
    IEmbeddingService,
    IQdrantService,
    IDocumentChunkRepository
)

logger = logging.getLogger(__name__)


# ===== STATE DEFINITION =====

class DocumentProcessingState(TypedDict, total=False):
    """State for document processing workflow."""
    # Input (required)
    filename: str
    content_bytes: bytes
    file_type: str  # .pdf, .txt, .md
    tenant_id: int
    user_id: int
    visibility: Literal["private", "tenant"]
    session_id: Optional[str]  # For WebSocket streaming
    enable_streaming: bool  # Enable WebSocket progress updates
    
    # Intermediate
    extracted_text: Optional[str]
    document_id: Optional[int]
    chunk_ids: List[int]
    embedding_count: int
    qdrant_point_ids: List[str]
    
    # Duplicate/Similarity Detection
    duplicate_document_id: Optional[int]
    duplicate_info: Optional[Dict[str, Any]]  # Duplicate document metadata
    similar_documents: List[Dict[str, Any]]   # List of similar docs
    user_decision: Optional[str]  # "replace" | "keep_both" | "cancel" 
    awaiting_decision: bool  # Workflow paused for user input
    
    # Temporary (workflow internal)
    _embedded_chunks: List[Dict[str, Any]]
    _original_chunks: List[Dict[str, Any]]
    
    # TOC-aware chunking (workflow internal)
    _toc: List[Tuple[int, str, int]]  # [(level, title, page_num), ...]
    _page_texts: Dict[int, str]       # {page_num: text}
    _has_structure: bool               # True if TOC extracted
    
    # Output
    status: str  # "success" | "failed"
    error: Optional[str]
    processing_summary: Dict[str, Any]


# ===== WORKFLOW CLASS =====

class DocumentProcessingWorkflow:
    """
    LangGraph-based document processing workflow.
    
    Automates entire document upload pipeline:
    1. File validation
    2. Content extraction (PDF/TXT/MD)
    3. Database storage
    4. Text chunking
    5. Embedding generation
    6. Qdrant upload
    7. Verification
    
    Benefits over manual process:
    - Single API call instead of 3 separate calls
    - Automatic error recovery
    - State tracking for debugging
    - Consistent processing pipeline
    """
    
    def __init__(
        self,
        doc_service: Optional[IDocumentService] = None,
        chunking_service: Optional[IChunkingService] = None,
        embedding_service: Optional[IEmbeddingService] = None,
        qdrant_service: Optional[IQdrantService] = None,
        chunk_repo: Optional[IDocumentChunkRepository] = None
    ):
        """
        Initialize workflow with dependency injection.
        
        Args:
            doc_service: Document service (default: creates new instance)
            chunking_service: Chunking service (default: creates new instance)
            embedding_service: Embedding service (default: creates new instance)
            qdrant_service: Qdrant service (default: creates new instance)
            chunk_repo: Chunk repository (default: creates new instance)
        """
        from core.dependencies import (
            get_document_service,
            get_chunking_service,
            get_embedding_service,
            get_qdrant_service,
            get_document_chunk_repository
        )
        
        self.doc_service = doc_service or get_document_service()
        self.chunking_service = chunking_service or get_chunking_service()
        self.embedding_service = embedding_service or get_embedding_service()
        self.qdrant_service = qdrant_service or get_qdrant_service()
        self.chunk_repo = chunk_repo or get_document_chunk_repository()
        
        self.graph = self._build_graph()
        logger.info("DocumentProcessingWorkflow initialized")
    
    def _build_graph(self) -> Any:
        """Build the LangGraph workflow with duplicate detection."""
        workflow = StateGraph(DocumentProcessingState)
        
        # Add nodes
        workflow.add_node("validate_file", self._validate_file_node)
        workflow.add_node("extract_content", self._extract_content_node)
        workflow.add_node("detect_duplicates", self._detect_duplicates_node)
        workflow.add_node("check_similarity", self._check_similarity_node)
        workflow.add_node("await_user_decision", self._await_user_decision_node)
        workflow.add_node("handle_replace_decision", self._handle_replace_decision_node)
        workflow.add_node("store_document", self._store_document_node)
        workflow.add_node("chunk_document", self._chunk_document_node)
        workflow.add_node("generate_embeddings", self._generate_embeddings_node)
        workflow.add_node("upsert_to_qdrant", self._upsert_qdrant_node)
        workflow.add_node("verify_completion", self._verify_completion_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Define entry point
        workflow.set_entry_point("validate_file")
        
        # Main workflow path with duplicate detection
        workflow.add_conditional_edges(
            "validate_file",
            self._check_validation,
            {
                "continue": "extract_content",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "extract_content",
            self._check_extraction,
            {
                "continue": "detect_duplicates",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "detect_duplicates",
            self._check_duplicate_detection,
            {
                "no_duplicates": "check_similarity",
                "duplicate_found": "await_user_decision",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "check_similarity",
            self._check_similarity_detection,
            {
                "no_similar": "store_document",
                "similar_found": "await_user_decision",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "await_user_decision",
            self._check_user_decision,
            {
                "replace": "handle_replace_decision",
                "keep_both": "store_document",
                "cancel": "verify_completion",  # Early exit
                "waiting": END,  # Exit workflow, await user decision via API
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_replace_decision",
            self._check_replace_handling,
            {
                "continue": "store_document",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "store_document",
            self._check_storage,
            {
                "continue": "chunk_document",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "chunk_document",
            self._check_chunking,
            {
                "continue": "generate_embeddings",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "generate_embeddings",
            self._check_embeddings,
            {
                "continue": "upsert_to_qdrant",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "upsert_to_qdrant",
            self._check_qdrant,
            {
                "continue": "verify_completion",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("verify_completion", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    # ===== NODE IMPLEMENTATIONS =====
    
    def _validate_file_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 1: Validate file parameters.
        
        Checks:
        - filename not empty
        - content_bytes not empty
        - file_type in allowed list
        - file size within limits
        """
        logger.info(f"[NODE: validate_file] Validating {state['filename']}")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "validate_file")
            
            # Check filename
            if not state.get("filename") or not state["filename"].strip():
                return {"error": "Filename is empty", "status": "failed"}
            
            # Check content
            if not state.get("content_bytes") or len(state["content_bytes"]) == 0:
                return {"error": "File content is empty", "status": "failed"}
            
            # Check file type
            allowed_types = {".pdf", ".txt", ".md"}
            if state["file_type"] not in allowed_types:
                return {"error": f"Invalid file type: {state['file_type']}", "status": "failed"}
            
            # Check file size (from config)
            config = ConfigService()
            max_size = config.get_max_file_size_mb() * 1024 * 1024
            if len(state["content_bytes"]) > max_size:
                return {"error": f"File too large: {len(state['content_bytes'])} bytes (max: {max_size})", "status": "failed"}
            
            logger.info(f"[NODE: validate_file] ✅ Validation passed")
            return {**state, "status": "validated"}  # Mark validation as complete
            
        except Exception as e:
            logger.error(f"[NODE: validate_file] ❌ Error: {e}", exc_info=True)
            return {"error": f"Validation error: {str(e)}", "status": "failed"}
    
    def _extract_content_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 2: Extract text content WITH structure (TOC, pages) from file bytes.
        
        Supports:
        - PDF (PyMuPDF for TOC + pages, PyPDF2 fallback)
        - TXT (UTF-8 detection)
        - MD (UTF-8)
        """
        logger.info(f"[NODE: extract_content] Extracting from {state['file_type']}")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "extract_content")
            
            # Try structured extraction (TOC-aware)
            structure_data = self.doc_service.extract_with_structure(
                state["content_bytes"],
                state["file_type"],
                state["filename"]
            )
            
            extracted_text = structure_data["full_text"]
            
            if not extracted_text or not extracted_text.strip():
                return {"error": "Extracted content is empty", "status": "failed"}
            
            logger.info(
                f"[NODE: extract_content] ✅ Extracted {len(extracted_text)} chars, "
                f"TOC: {len(structure_data.get('toc', []))} entries, "
                f"Structure: {'Yes' if structure_data.get('has_structure') else 'No'}"
            )
            
            return {
                "extracted_text": extracted_text,
                "_toc": structure_data.get("toc", []),
                "_page_texts": structure_data.get("page_texts", {}),
                "_has_structure": structure_data.get("has_structure", False)
            }
            
        except Exception as e:
            logger.error(f"[NODE: extract_content] ❌ Error: {e}", exc_info=True)
            return {"error": f"Content extraction failed: {str(e)}", "status": "failed"}
    
    def _store_document_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 3: Store document in PostgreSQL documents table.
        """
        logger.info(f"[NODE: store_document] Storing {state['filename']}")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "store_document")
            
            doc_id = self.doc_service.repository.insert_document(
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                visibility=state["visibility"],
                source="upload",
                title=state["filename"],
                content=state["extracted_text"]
            )
            
            logger.info(f"[NODE: store_document] ✅ Document stored: id={doc_id}")
            return {**state, "document_id": doc_id}
            
        except Exception as e:
            logger.error(f"[NODE: store_document] ❌ Error: {e}", exc_info=True)
            return {"error": f"Database storage failed: {str(e)}", "status": "failed"}
    
    def _chunk_document_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 4: Smart chunking with TOC awareness.
        
        Uses chunk_document_with_structure if TOC available, otherwise fallback.
        """
        logger.info(f"[NODE: chunk_document] Chunking document_id={state['document_id']}")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "chunk_document")
            
            # Check if TOC is available
            has_structure = state.get("_has_structure", False)
            toc = state.get("_toc", [])
            page_texts = state.get("_page_texts", {})
            
            # DEBUG: Log state keys
            logger.info(f"[DEBUG] State keys present: {list(state.keys())}")
            logger.info(f"[DEBUG] _has_structure={has_structure}, toc_length={len(toc)}, page_texts_keys={len(page_texts)}")
            
            if has_structure and toc:
                # Smart chunking with TOC
                logger.info(f"[NODE: chunk_document] Using TOC-aware chunking")
                chunk_ids = self.chunking_service.chunk_document_with_structure(
                    document_id=state["document_id"],
                    tenant_id=state["tenant_id"],
                    content=state["extracted_text"],
                    source_title=state["filename"],
                    toc=toc,
                    page_texts=page_texts
                )
            else:
                # Fallback: standard character-based chunking
                logger.info(f"[NODE: chunk_document] Using fallback character-based chunking")
                chunk_ids = self.chunking_service.chunk_document(
                    document_id=state["document_id"],
                    tenant_id=state["tenant_id"],
                    content=state["extracted_text"],
                    source_title=state["filename"]
                )
            
            logger.info(f"[NODE: chunk_document] ✅ Created {len(chunk_ids)} chunks")
            return {"chunk_ids": chunk_ids}
            
        except Exception as e:
            logger.error(f"[NODE: chunk_document] ❌ Error: {e}", exc_info=True)
            return {"error": f"Chunking failed: {str(e)}", "status": "failed"}
    
    def _generate_embeddings_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 5: Generate embeddings for all chunks.
        """
        logger.info(f"[NODE: generate_embeddings] Processing {len(state['chunk_ids'])} chunks")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "generate_embeddings")
            # Fetch chunks
            chunks = self.chunk_repo.get_chunks_not_embedded(
                document_id=state["document_id"]
            )
            
            if not chunks:
                state["error"] = "No chunks found to embed"
                state["status"] = "failed"
                return state
            
            # Generate embeddings
            embedded_chunks = self.embedding_service.generate_embeddings_for_chunks(chunks)
            
            logger.info(f"[NODE: generate_embeddings] ✅ Generated {len(embedded_chunks)} embeddings")
            
            # Store for next node
            return {
                "embedding_count": len(embedded_chunks),
                "_embedded_chunks": embedded_chunks,
                "_original_chunks": chunks
            }
            
        except Exception as e:
            logger.error(f"[NODE: generate_embeddings] ❌ Error: {e}", exc_info=True)
            return {"error": f"Embedding generation failed: {str(e)}", "status": "failed"}
    
    def _upsert_qdrant_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 6: Upload embeddings to Qdrant with batching.
        """
        logger.info(f"[NODE: upsert_to_qdrant] Uploading {state['embedding_count']} vectors")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "upsert_to_qdrant")
            embedded_chunks = state.get("_embedded_chunks", [])
            original_chunks = state.get("_original_chunks", [])
            
            # Prepare Qdrant data
            qdrant_data = []
            for embedded_chunk in embedded_chunks:
                original = next(
                    (c for c in original_chunks if c["id"] == embedded_chunk["chunk_id"]),
                    None
                )
                
                if original:
                    qdrant_data.append({
                        "chunk_id": embedded_chunk["chunk_id"],
                        "embedding": embedded_chunk["embedding"],
                        "tenant_id": original["tenant_id"],
                        "document_id": original["document_id"],
                        "user_id": state.get("user_id"),  # Document owner
                        "visibility": state.get("visibility", "tenant"),  # Access control
                        "content": original["content"],
                        # TOC metadata (NEW)
                        "chapter_name": original.get("chapter_name"),
                        "page_start": original.get("page_start"),
                        "page_end": original.get("page_end"),
                        "section_level": original.get("section_level")
                    })
            
            # Upsert to Qdrant (with automatic batching to avoid payload size limits)
            qdrant_results = self.qdrant_service.upsert_document_chunks(
                qdrant_data,
                batch_size=self.qdrant_service.upload_batch_size
            )
            
            # Update PostgreSQL with point IDs
            self.chunk_repo.update_chunks_embedding_batch(qdrant_results)
            
            logger.info(f"[NODE: upsert_to_qdrant] ✅ Uploaded {len(qdrant_results)} vectors")
            return {"qdrant_point_ids": [r["qdrant_point_id"] for r in qdrant_results]}
            
        except Exception as e:
            logger.error(f"[NODE: upsert_to_qdrant] ❌ Error: {e}", exc_info=True)
            return {"error": f"Qdrant upload failed: {str(e)}", "status": "failed"}
    
    def _verify_completion_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node 7: Verify all steps completed successfully.
        """
        logger.info(f"[NODE: verify_completion] Verifying document_id={state['document_id']}")
        
        try:
            # Broadcast progress
            self._broadcast_progress(state, "verify_completion")
            processing_summary = {
                "document_id": state["document_id"],
                "filename": state["filename"],
                "content_length": len(state["extracted_text"]),
                "chunk_count": len(state["chunk_ids"]),
                "embedding_count": state["embedding_count"],
                "qdrant_vectors": len(state["qdrant_point_ids"])
            }
            
            logger.info(f"[NODE: verify_completion] ✅ Processing complete")
            return {"status": "success", "processing_summary": processing_summary}
            
        except Exception as e:
            logger.error(f"[NODE: verify_completion] ❌ Error: {e}", exc_info=True)
            return {"error": f"Verification failed: {str(e)}", "status": "failed"}
    
    def _handle_error_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Error handler node.
        """
        logger.error(f"[NODE: handle_error] Pipeline failed: {state.get('error', 'Unknown error')}")
        
        processing_summary = {
            "error": state.get("error", "Unknown error"),
            "document_id": state.get("document_id"),
            "filename": state.get("filename"),
            "completed_steps": []
        }
        
        # Track which steps completed
        if state.get("extracted_text"):
            processing_summary["completed_steps"].append("extraction")
        if state.get("document_id"):
            processing_summary["completed_steps"].append("storage")
        if state.get("chunk_ids"):
            processing_summary["completed_steps"].append("chunking")
        if state.get("embedding_count"):
            processing_summary["completed_steps"].append("embedding")
        
        return {"status": "failed", "processing_summary": processing_summary}
    
    # ===== ROUTING FUNCTIONS =====
    
    def _check_validation(self, state: DocumentProcessingState) -> str:
        """Check if validation passed."""
        if state.get("error"):
            return "error"
        return "continue"
    
    def _check_extraction(self, state: DocumentProcessingState) -> str:
        """Check if content extraction succeeded."""
        if state.get("error") or not state.get("extracted_text"):
            return "error"
        return "continue"
    
    def _check_storage(self, state: DocumentProcessingState) -> str:
        """Check if document storage succeeded."""
        if state.get("error") or not state.get("document_id"):
            return "error"
        return "continue"
    
    def _check_chunking(self, state: DocumentProcessingState) -> str:
        """Check if chunking succeeded."""
        if state.get("error") or not state.get("chunk_ids"):
            return "error"
        return "continue"
    
    def _check_embeddings(self, state: DocumentProcessingState) -> str:
        """Check if embedding generation succeeded."""
        if state.get("error") or state.get("embedding_count", 0) == 0:
            return "error"
        return "continue"
    
    def _check_qdrant(self, state: DocumentProcessingState) -> str:
        """Check if Qdrant upload succeeded."""
        if state.get("error") or not state.get("qdrant_point_ids"):
            return "error"
        return "continue"

    # ===== NEW DUPLICATE DETECTION ROUTING FUNCTIONS =====
    
    def _check_duplicate_detection(self, state: DocumentProcessingState) -> str:
        """Check duplicate detection results."""
        if state.get("error"):
            return "error"
        if state.get("duplicate_document_id"):
            return "duplicate_found"
        return "no_duplicates"
    
    def _check_similarity_detection(self, state: DocumentProcessingState) -> str:
        """Check similarity detection results."""
        if state.get("error"):
            return "error"
        if state.get("similar_documents") and len(state["similar_documents"]) > 0:
            return "similar_found"
        return "no_similar"
    
    def _check_user_decision(self, state: DocumentProcessingState) -> str:
        """Check user decision status."""
        if state.get("error"):
            return "error"
        
        decision = state.get("user_decision")
        if not decision and state.get("awaiting_decision"):
            return "waiting"
        
        if decision == "replace":
            return "replace"
        elif decision == "keep_both":
            return "keep_both"
        elif decision == "cancel":
            return "cancel"
        
        return "waiting"
    
    def _check_replace_handling(self, state: DocumentProcessingState) -> str:
        """Check if replace handling succeeded."""
        if state.get("error"):
            return "error"
        return "continue"

    # ===== NEW DUPLICATE DETECTION NODE IMPLEMENTATIONS =====
    
    def _detect_duplicates_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node: Detect if document already exists (content-based duplicate detection).
        
        Checks for documents with same content prefix (first 500 chars) in the same tenant/user scope.
        This is more accurate than filename-based detection and faster than full similarity search.
        """
        logger.info(f"[NODE: detect_duplicates] Checking for content-based duplicates of {state['filename']}")
        
        try:
            # Skip if no extracted text yet
            if not state.get("extracted_text"):
                logger.info(f"[NODE: detect_duplicates] No extracted text available for duplicate check")
                return {"duplicate_document_id": None}  # Explicitly mark no duplicates - no text
            
            # Use first 500 characters for duplicate detection
            content_prefix = state["extracted_text"][:500].strip()
            if not content_prefix:
                logger.info(f"[NODE: detect_duplicates] Content too short for duplicate check")
                return {"duplicate_document_id": None}  # Explicitly mark no duplicates - content too short
            
            # Query database for existing documents with same content prefix
            from database.pg_connection import get_db_connection
            
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    query = """
                        SELECT d.id, d.title, d.created_at, u.nickname
                        FROM documents d
                        LEFT JOIN users u ON d.user_id = u.user_id
                        WHERE d.tenant_id = %s 
                        AND LEFT(d.content, 500) = %s
                        AND d.id != %s
                        AND (
                            (d.visibility = 'tenant') OR 
                            (d.visibility = 'private' AND d.user_id = %s)
                        )
                        ORDER BY d.created_at DESC
                        LIMIT 1
                    """
                    
                    cursor.execute(query, (
                        state["tenant_id"],
                        content_prefix,
                        state.get("document_id", -1),  # Exclude current doc if updating
                        state["user_id"]
                    ))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        doc_id, doc_title, created_at, owner_nickname = result
                        
                        duplicate_info = {
                            "document_id": doc_id,
                            "title": doc_title,
                            "uploaded_at": created_at.isoformat() if created_at else None,
                            "owner_nickname": owner_nickname or "Unknown",
                            "is_same_user": state["user_id"] == state["user_id"]  # TODO: Get actual owner_id
                        }
                        
                        logger.info(f"[NODE: detect_duplicates] Duplicate found: {doc_id}")
                        
                        # Broadcast duplicate detection to WebSocket
                        self._broadcast_progress(state, "detect_duplicates", {
                            "type": "duplicate_detected",
                            "duplicate_info": duplicate_info
                        })
                        
                        return {
                            "duplicate_document_id": doc_id,
                            "duplicate_info": duplicate_info,
                            "awaiting_decision": True
                        }
                    else:
                        logger.info(f"[NODE: detect_duplicates] No duplicates found")
                        self._broadcast_progress(state, "detect_duplicates")
                        return {"duplicate_document_id": None}  # Explicitly mark no duplicates
                    
        except Exception as e:
            logger.error(f"[NODE: detect_duplicates] Error: {e}", exc_info=True)
            return {"error": f"Duplicate detection failed: {str(e)}", "status": "failed"}
    
    def _check_similarity_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node: Check for similar documents using embeddings.
        
        Uses vector similarity search to find potentially related documents.
        """
        logger.info(f"[NODE: check_similarity] Checking for similar documents")
        
        try:
            # Skip similarity check if no extracted text
            if not state.get("extracted_text"):
                logger.info(f"[NODE: check_similarity] No text to check similarity")
                return {"similar_documents": []}  # Explicitly mark no similar docs
            
            # Use Qdrant to find similar documents
            extracted_text = state["extracted_text"][:1000]  # Use first 1000 chars for similarity
            
            # Generate embedding for similarity search
            embedding = self.embedding_service.generate_embedding(extracted_text)
            
            # Create search request
            from services.qdrant_service import SearchDocumentChunksRequest
            search_request = SearchDocumentChunksRequest(
                query_vector=embedding,
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                limit=3,
                score_threshold=0.99  # Extremely high threshold - only truly identical docs
            )
            
            # Search for similar vectors in Qdrant
            search_results = self.qdrant_service.search_document_chunks(search_request)
            
            similar_docs = []
            for result in search_results:
                if result.get("score", 0) > 0.85:  # Only highly similar docs
                    similar_docs.append({
                        "document_id": result.get("document_id"),
                        "title": result.get("title", "Unknown"),
                        "similarity_score": result.get("score", 0),
                        "chunk_preview": result.get("content", "")[:200]
                    })
            
            if similar_docs:
                logger.info(f"[NODE: check_similarity] Found {len(similar_docs)} similar documents")
                
                # Broadcast similarity detection to WebSocket
                self._broadcast_progress(state, "check_similarity", {
                    "type": "similar_detected",
                    "similar_docs": similar_docs
                })
                
                return {
                    "similar_documents": similar_docs,
                    "awaiting_decision": True
                }
            else:
                logger.info(f"[NODE: check_similarity] No similar documents found")
                self._broadcast_progress(state, "check_similarity")
                return {"similar_documents": []}  # Explicitly mark no similar documents found
                
        except Exception as e:
            logger.error(f"[NODE: check_similarity] Error: {e}", exc_info=True)
            return {"error": f"Similarity check failed: {str(e)}", "status": "failed"}
    
    def _await_user_decision_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node: Wait for user decision on duplicate/similar documents.
        
        This node loops until user provides a decision via WebSocket.
        """
        logger.info(f"[NODE: await_user_decision] Waiting for user decision")
        
        try:
            # Check if we already have a decision
            if state.get("user_decision"):
                logger.info(f"[NODE: await_user_decision] Decision received: {state['user_decision']}")
                return {"awaiting_decision": False}
            
            # If no decision yet, keep waiting
            logger.info(f"[NODE: await_user_decision] Still waiting for decision...")
            return {"awaiting_decision": True}
            
        except Exception as e:
            logger.error(f"[NODE: await_user_decision] Error: {e}", exc_info=True)
            return {"error": f"Decision waiting failed: {str(e)}", "status": "failed"}
    
    def _handle_replace_decision_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """
        Node: Handle document replacement (archive old version).
        """
        logger.info(f"[NODE: handle_replace_decision] Handling replace decision")
        
        try:
            duplicate_id = state.get("duplicate_document_id")
            if not duplicate_id:
                return {"error": "No duplicate document ID to replace", "status": "failed"}
            
            # Archive the old document (soft delete or move to archive)
            from database.pg_connection import get_db_connection
            
            with get_db_connection() as db:
                # Update old document to archived status
                query = """
                    UPDATE documents 
                    SET title = title || '_archived_' || EXTRACT(EPOCH FROM NOW())::bigint,
                        visibility = 'private',
                        updated_at = NOW()
                    WHERE id = %s
                """
                cursor = db.cursor()
                cursor.execute(query, (duplicate_id,))
                db.commit()
                
                logger.info(f"[NODE: handle_replace_decision] Archived document {duplicate_id}")
                
            return {"duplicate_document_id": None, "duplicate_info": None}
            
        except Exception as e:
            logger.error(f"[NODE: handle_replace_decision] Error: {e}", exc_info=True)
            return {"error": f"Replace handling failed: {str(e)}", "status": "failed"}
    
    # ===== HELPER METHODS =====
    
    # Store the main event loop reference for cross-thread async calls
    _main_event_loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _broadcast_progress(self, state: DocumentProcessingState, node_name: str, extra_data: Dict = None):
        """Broadcast workflow progress via WebSocket if streaming enabled."""
        if not state.get("enable_streaming") or not state.get("session_id"):
            return
        
        try:
            # Prepare state data for broadcast (remove sensitive info)
            broadcast_state = {
                "filename": state.get("filename"),
                "status": state.get("status"),
                "document_id": state.get("document_id"),
                "chunk_ids_count": len(state.get("chunk_ids", [])),
                "embedding_count": state.get("embedding_count", 0)
            }
            
            # Add extra data if provided
            if extra_data:
                broadcast_state.update(extra_data)
            
            # Use the main event loop (stored when process_document starts)
            if self._main_event_loop and self._main_event_loop.is_running():
                # Schedule async broadcast on the main event loop
                future = asyncio.run_coroutine_threadsafe(
                    websocket_manager.broadcast_state(
                        state["session_id"], 
                        node_name, 
                        broadcast_state
                    ),
                    self._main_event_loop
                )
                # Don't wait for result - fire and forget
                logger.debug(f"[BROADCAST] Scheduled for node: {node_name}")
            else:
                logger.warning(f"[BROADCAST] Main event loop not available for node: {node_name}")
            
        except Exception as e:
            logger.warning(f"Failed to broadcast progress: {e}")
    
    # ===== SESSION-BASED DECISION HANDLING =====
    
    _session_states: Dict[str, DocumentProcessingState] = {}
    
    def set_user_decision(self, session_id: str, decision: str, document_id: Optional[int] = None):
        """
        Set user decision for a specific session.
        
        Called from the upload-decision endpoint.
        """
        if session_id in self._session_states:
            self._session_states[session_id]["user_decision"] = decision
            if document_id:
                self._session_states[session_id]["duplicate_document_id"] = document_id
            
            logger.info(f"Decision set for session {session_id}: {decision}")
        else:
            logger.warning(f"No active workflow for session {session_id}")
    
    # ===== EXECUTION =====
    
    async def process_document(
        self,
        filename: str,
        content: bytes,
        file_type: str,
        tenant_id: int,
        user_id: int,
        visibility: Literal["private", "tenant"],
        session_id: Optional[str] = None,
        enable_streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the full document processing workflow with duplicate detection.
        
        Args:
            filename: Original filename
            content: File bytes
            file_type: .pdf, .txt, .md
            tenant_id: Tenant ID
            user_id: User ID
            visibility: Document visibility level
            session_id: Session ID for WebSocket streaming
            enable_streaming: Enable real-time progress updates
        
        Returns:
            {
                "status": "success" | "failed" | "awaiting_decision",
                "document_id": int,
                "summary": {...}
            }
        
        Raises:
            Exception: If workflow execution fails
        """
        initial_state = DocumentProcessingState(
            filename=filename,
            content_bytes=content,
            file_type=file_type,
            tenant_id=tenant_id,
            user_id=user_id,
            visibility=visibility,
            session_id=session_id,
            enable_streaming=enable_streaming,
            extracted_text=None,
            document_id=None,
            chunk_ids=[],
            embedding_count=0,
            qdrant_point_ids=[],
            duplicate_document_id=None,
            duplicate_info=None,
            similar_documents=[],
            user_decision=None,
            awaiting_decision=False,
            status="processing",
            error=None,
            processing_summary={}
        )
        
        logger.info(f"[WORKFLOW] Starting document processing: {filename} (session: {session_id})")
        
        # Store the main event loop for cross-thread async broadcasts
        try:
            self._main_event_loop = asyncio.get_running_loop()
            logger.info(f"[WORKFLOW] Main event loop captured for WebSocket broadcasts")
        except RuntimeError:
            self._main_event_loop = None
            logger.warning("[WORKFLOW] No running event loop - broadcasts will be disabled")
        
        try:
            # Setup streaming if enabled
            if enable_streaming and session_id:
                logger.info(f"[WORKFLOW] WebSocket streaming enabled for session {session_id}")
            
            # Use ainvoke (async) to allow event loop to process broadcasts between nodes
            final_state = await self.graph.ainvoke(initial_state)
            
            # Build summary from final state (regardless of completion status)
            summary = final_state.get("processing_summary", {})
            if not summary and final_state.get("document_id"):  # Build summary if not set
                summary = {
                    "document_id": final_state.get("document_id"),
                    "filename": final_state.get("filename"),
                    "content_length": len(final_state.get("extracted_text", "")),
                    "chunk_count": len(final_state.get("chunk_ids", [])),
                    "embedding_count": final_state.get("embedding_count", 0),
                    "qdrant_vectors": len(final_state.get("qdrant_point_ids", []))
                }
            
            logger.info(f"[WORKFLOW] Processing complete: status={final_state['status']}")
            
            return {
                "status": final_state["status"],
                "document_id": final_state.get("document_id"),
                "error": final_state.get("error"),
                "summary": summary,
                "duplicate_info": final_state.get("duplicate_info"),
                "similar_documents": final_state.get("similar_documents")
            }
            
        except Exception as e:
            logger.error(f"[WORKFLOW] Fatal error: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": f"Workflow execution failed: {str(e)}",
                "summary": {}
            }
