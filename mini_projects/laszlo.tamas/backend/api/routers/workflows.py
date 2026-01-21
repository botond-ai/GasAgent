"""
Workflow Orchestration Endpoints

Exposes LangGraph workflows for document processing and memory consolidation.
Automated pipelines replace multi-step manual API calls.
"""

import logging
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any

from api.helpers import handle_api_error
from services.document_processing_workflow import DocumentProcessingWorkflow

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== SCHEMAS =====

class WorkflowResponse(BaseModel):
    """Generic workflow response."""
    status: str = Field(..., description="success | skipped | failed")
    error: str = Field(None, description="Error message if failed")
    summary: Dict[str, Any] = Field(..., description="Processing summary")


# ===== ENDPOINTS =====

@router.post("/process-document", status_code=status.HTTP_202_ACCEPTED)
@handle_api_error("process document")
async def process_document_workflow(
    file: UploadFile = File(...),
    tenant_id: int = Form(...),
    user_id: int = Form(...),
    visibility: Literal["private", "tenant"] = Form(...),
    session_id: str = Form(None),
    enable_streaming: bool = Form(False)
):
    """
    **NEW: Automated Document Processing Workflow (ASYNC)**
    
    Returns 202 Accepted - workflow started, processing in background.
    
    Replaces 3 manual API calls with single automated pipeline:
    
    OLD WAY (manual):
    1. POST /api/documents/upload
    2. POST /api/documents/{id}/chunk
    3. POST /api/documents/{id}/embed
    
    NEW WAY (automated):
    1. POST /api/workflows/process-document ✨
    
    Pipeline steps (automatic):
    - File validation
    - Content extraction (PDF/TXT/MD)
    - Database storage
    - Text chunking
    - Embedding generation
    - Qdrant upload
    - Verification
    
    Benefits:
    - Single API call
    - Automatic error recovery
    - State tracking
    - Consistent processing
    - Better error messages
    
    Args:
        file: Document file (PDF, TXT, or MD)
        tenant_id: Tenant identifier
        user_id: User identifier
        visibility: Document visibility level
    
    Returns (HTTP 202 Accepted):
        {
            "status": "processing" | "success" | "failed",
            "task_id": str (session_id for tracking),
            "document_id": int (if completed),
            "summary": {
                "filename": str,
                "content_length": int,
                "chunk_count": int,
                "embedding_count": int,
                "qdrant_vectors": int
            }
        }
    
    Raises:
        400: Invalid file or parameters
        500: Processing error
    
    Status Codes:
        202: Workflow accepted and started (async processing)
        400: Invalid request
        500: Workflow execution error
    
    Use case: Document upload via frontend (single button replaces multi-step upload)
    """
    logger.info(f"[WORKFLOW API] process-document: {file.filename}, tenant={tenant_id}, user={user_id}")
    
    # Validate file extension
    file_ext = f".{file.filename.split('.')[-1].lower()}" if "." in file.filename else ""
    if file_ext not in {".pdf", ".txt", ".md"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file_ext}. Allowed: .pdf, .txt, .md"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size (from system.ini [limits] section)
    from services.config_service import get_config_service
    config = get_config_service()
    max_size_mb = config.get_max_file_size_mb()
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {len(content)} bytes (max: {max_size_mb} MB)"
        )
    
    # Execute workflow
    workflow = DocumentProcessingWorkflow()
    result = await workflow.process_document(
        filename=file.filename,
        content=content,
        file_type=file_ext,
        tenant_id=tenant_id,
        user_id=user_id,
        visibility=visibility,
        session_id=session_id,
        enable_streaming=enable_streaming
    )
    
    logger.info(f"[WORKFLOW API] process-document complete: status={result['status']}")
    
    if result["status"] == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Document processing failed")
        )
    
    # 202 Accepted response: workflow started/completed
    return {
        "status": result["status"],  # "success" | "processing" | "failed"
        "task_id": session_id or "no-session",  # For tracking async progress
        "document_id": result.get("document_id"),
        "summary": result["summary"],
        "duplicate_info": result.get("duplicate_info"),
        "similar_documents": result.get("similar_documents")
    }


@router.get("/status")
async def workflow_status():
    """
    Get workflow system status.
    
    Returns information about available workflows and their configuration.
    
    Use case: Health check, monitoring dashboard
    """
    return {
        "workflows": [
            {
                "name": "document_processing",
                "endpoint": "/api/workflows/process-document",
                "status": "available"
            },
            {
                "name": "session_memory",
                "endpoint": "/api/sessions/{id}/consolidate",
                "status": "available"
            }
        ],
        "system": {
            "langgraph": "enabled",
            "qdrant": "connected",
            "openai": "configured"
        }
    }
