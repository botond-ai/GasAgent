"""
Document Management Endpoints

Handles document CRUD operations and access control.
Documents support multi-tenant isolation and visibility levels (private/tenant).
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends, status, Response
from pydantic import BaseModel, Field, ConfigDict

from api.helpers import (
    handle_api_error,
    NotFoundError,
    ForbiddenError,
    validate_resource_exists,
    validate_ownership,
    validate_tenant_isolation
)
from api.dependencies import verify_document_access
from database.pg_init import (
    get_documents_for_user,
    get_document_by_id,
    delete_document
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== SCHEMAS =====

class DocumentSummary(BaseModel):
    """Summary of a document (without full content)."""
    id: int
    tenant_id: int
    user_id: Optional[int] = None
    visibility: str
    source: str
    title: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(BaseModel):
    """Full document with content."""
    id: int
    tenant_id: int
    user_id: Optional[int] = None
    visibility: str
    source: str
    title: str
    content: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """Response for document list."""
    documents: List[DocumentSummary]
    count: int


# ===== ENDPOINTS =====

@router.get("", response_model=DocumentListResponse)
@handle_api_error("list documents")
def list_documents(
    user_id: int = Query(..., description="User ID"),
    tenant_id: int = Query(..., description="Tenant ID")
):
    """
    List all documents accessible to the user.
    
    Includes:
        - Private documents owned by the user
        - Tenant-wide documents in the user's tenant
    
    Returns:
        Document metadata without full content
    
    Use case: Document library, file picker
    """
    logger.info(f"Listing documents for user {user_id}, tenant {tenant_id}")
    
    documents = get_documents_for_user(user_id=user_id, tenant_id=tenant_id)
    
    logger.info(f"Found {len(documents)} documents for user {user_id}")
    
    return DocumentListResponse(
        documents=documents,
        count=len(documents)
    )


@router.get("/{document_id}", response_model=DocumentDetail)
@handle_api_error("fetch document")
def get_document(
    document_id: int,
    user_id: int = Query(..., description="User ID"),
    tenant_id: int = Query(..., description="Tenant ID"),
    document: dict = Depends(verify_document_access)
):
    """
    Get full document by ID including content.
    
    Permission check: Verifies user has read access to document.
    - Owner: Full access
    - Private documents: Owner only
    - Tenant documents: All tenant users (read access)
    
    Returns:
        Full document with content field
    
    Raises:
        404: Document not found
        403: Access denied
    
    Use case: Document viewer, full-text search preview
    """
    logger.info(f"Fetching document {document_id} for user {user_id}")
    
    # document already fetched and verified by verify_document_access
    # Just return the full document from DB (verify_document_access returns metadata only)
    
    # Fetch full document (with content)
    full_document = get_document_by_id(document_id)
    
    logger.info(f"Retrieved document {document_id}: {full_document['title']}")
    
    return full_document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_error("delete document")
async def remove_document(
    document_id: int,
    user_id: int = Query(..., description="User ID"),
    tenant_id: int = Query(..., description="Tenant ID")
):
    """
    Delete a document and all its chunks.
    
    Permission check: Manual verification (owner only).
    - Tenant documents: Owner only (even if visible to all)
    - Private documents: Owner only
    
    Side effects:
        - Deletes document_chunks (cascade)
        - Removes Qdrant vectors (should be handled by service)
    
    Returns:
        204 No Content (empty body) on success
    
    Raises:
        404: Document not found
        403: Access denied (not owner)
    
    Status Codes:
        204: Document successfully deleted (no content returned)
        403: Forbidden - not document owner
        404: Document not found
    
    Use case: Document library cleanup, GDPR deletion
    """
    logger.info(f"Deleting document {document_id} by user {user_id}")
    
    # Fetch and verify
    document = get_document_by_id(document_id)
    validate_resource_exists(document, "Document", document_id)
    
    # Verify tenant isolation
    validate_tenant_isolation(document, tenant_id)
    
    # Verify ownership (only owner can delete)
    validate_ownership(document, user_id)
    
    delete_document(document_id)
    
    logger.info(f"✅ Deleted document {document_id}: {document['title']}")
    
    # 204 No Content - empty body (REST best practice)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/upload-decision", response_model=dict)
@handle_api_error("handle upload decision")
def handle_upload_decision(
    session_id: str = Query(..., description="Session ID"),
    decision: str = Query(..., description="User decision: replace, keep_both, cancel"),
    document_id: Optional[int] = Query(None, description="Document ID for replace decision")
):
    """
    Handle user decision for duplicate/similar document uploads.
    
    Called when user makes a decision in the document upload workflow
    after duplicate or similar documents are detected.
    
    Args:
        session_id: Upload session identifier
        decision: User choice (replace, keep_both, cancel)
        document_id: ID of document to replace (required for 'replace' decision)
    
    Returns:
        {"status": "success", "message": "Decision processed"}
    
    Use case: Document upload duplicate detection workflow
    """
    logger.info(f"Upload decision for session {session_id}: {decision}")
    
    # Validate decision
    valid_decisions = {"replace", "keep_both", "cancel"}
    if decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision: {decision}. Must be one of: {valid_decisions}"
        )
    
    # Validate document_id for replace decision
    if decision == "replace" and not document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id is required for 'replace' decision"
        )
    
    try:
        # Import here to avoid circular imports
        from services.document_processing_workflow import DocumentProcessingWorkflow
        
        # Create workflow instance and set decision
        workflow = DocumentProcessingWorkflow()
        workflow.set_user_decision(session_id, decision, document_id)
        
        logger.info(f"Decision processed for session {session_id}: {decision}")
        
        return {
            "status": "success",
            "message": f"Decision '{decision}' processed for session {session_id}",
            "session_id": session_id,
            "decision": decision
        }
        
    except Exception as e:
        logger.error(f"Error processing decision for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process decision: {str(e)}"
        )
