"""
Dependency Injection Providers - REFACTORED

This file now provides TWO types of dependencies:
1. Service injection (cache, workflows) - NEW
2. Permission verification (documents) - LEGACY (kept)
"""

import os
import logging
from typing import Optional, Literal
from fastapi import Query, status

from api.helpers import handle_api_error
from services.cache_service import simple_cache
from services.unified_chat_workflow import UnifiedChatWorkflow
from services.exceptions import (
    ConfigurationError, 
    ValidationError,
    DocumentServiceError,
    AuthorizationError
)
from api.helpers.error_handlers import NotFoundError
from database.pg_init import get_document_by_id

logger = logging.getLogger(__name__)

# ===== WORKFLOW INITIALIZATION (NEW) =====

_unified_workflow: Optional[UnifiedChatWorkflow] = None


def init_workflows():
    """Initialize workflows on application startup."""
    global _unified_workflow
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    logger.warning(f"🔍 init_workflows() called")
    logger.warning(f"   OPENAI_API_KEY present: {bool(openai_api_key)}")
    logger.warning(f"   _unified_workflow before: {_unified_workflow}")
    
    if openai_api_key:
        _unified_workflow = UnifiedChatWorkflow(openai_api_key)
        logger.warning(f"✅ UnifiedChatWorkflow initialized: {_unified_workflow}")
    else:
        logger.warning("⚠️ OPENAI_API_KEY not set, workflows disabled")


# ===== SERVICE PROVIDERS (NEW) =====

def get_cache_service():
    """
    Provide cache service instance.
    
    Usage:
        @router.get("/resource")
        async def get_resource(cache = Depends(get_cache_service)):
            cached = cache.get("key")
    """
    return simple_cache


def get_chat_workflow() -> Optional[UnifiedChatWorkflow]:
    """
    Provide UnifiedChatWorkflow instance.
    
    Returns None if OPENAI_API_KEY not configured.
    
    Usage:
        @router.post("/chat")
        async def chat(workflow = Depends(get_chat_workflow)):
            if not workflow:
                raise HTTPException(503, "Chat service unavailable")
    """
    return _unified_workflow


def require_chat_workflow() -> UnifiedChatWorkflow:
    """
    Provide UnifiedChatWorkflow or raise ConfigurationError if unavailable.
    
    Usage:
        @router.post("/chat")
        async def chat(workflow = Depends(require_chat_workflow)):
            # workflow guaranteed to be non-None
    """
    workflow = get_chat_workflow()
    if not workflow:
        raise ConfigurationError(
            "Chat service unavailable. OPENAI_API_KEY not configured.",
            context={"service": "chat_workflow", "reason": "missing_api_key"}
        )
    return workflow


# ===== PERMISSION VERIFICATION (LEGACY - KEPT) =====

async def verify_document_access(
    document_id: int,
    user_id: int = Query(..., description="User ID requesting access"),
    tenant_id: int = Query(..., description="Tenant ID of the user"),
    required_permission: Literal["read", "write", "delete"] = "read"
) -> dict:
    """
    Dependency: Verify user has access to a specific document.
    
    Access rules:
    1. Document must belong to the same tenant as the user
    2. Owner (documents.user_id) always has full access
    3. Private documents: only owner can access
    4. Tenant-wide documents: all tenant users have read access
    
    Args:
        document_id: ID of the document to access
        user_id: ID of the user requesting access
        tenant_id: ID of the tenant the user belongs to
        required_permission: Minimum permission level required (default: "read")
    
    Returns:
        dict: Document metadata
    
    Raises:
        NotFoundError: Document not found
        ForbiddenError: Access denied (insufficient permissions)
    
    Example:
        @router.get("/{document_id}", dependencies=[Depends(verify_document_access)])
        async def get_document(document_id: int):
            ...
    """
    # Fetch document
    document = get_document_by_id(document_id)
    if not document:
        raise NotFoundError("Document", document_id)
    
    # 1. Tenant isolation: document must belong to user's tenant
    doc_tenant_id = document.get("tenant_id")
    if doc_tenant_id != tenant_id:
        logger.warning(
            f"Tenant mismatch: user {user_id} (tenant {tenant_id}) "
            f"tried to access document {document_id} (tenant {doc_tenant_id})"
        )
        raise AuthorizationError(
            "Access denied: tenant mismatch",
            context={
                "document_id": document_id,
                "user_tenant": tenant_id,
                "document_tenant": doc_tenant_id,
                "user_id": user_id
            }
        )
    
    # 2. Owner check: owner has full access
    doc_user_id = document.get("user_id")
    is_owner = (doc_user_id == user_id)
    
    if is_owner:
        logger.info(f"✅ Owner access: user {user_id} → document {document_id}")
        return document
    
    # 3. Visibility check: if private, only owner can access
    visibility = document.get("visibility", "private")
    if visibility == "private":
        logger.warning(
            f"Private document {document_id}: user {user_id} is not owner (owner={doc_user_id})"
        )
        raise AuthorizationError(
            "Access denied: private document",
            context={
                "document_id": document_id,
                "visibility": visibility,
                "user_id": user_id,
                "document_owner": doc_user_id
            }
        )
    
    # 4. Tenant-wide documents: read access for all tenant users
    if visibility == "tenant":
        if required_permission == "read":
            logger.info(f"✅ Tenant access: user {user_id} → tenant document {document_id}")
            return document
        else:
            logger.warning(
                f"Insufficient permissions: user {user_id} needs '{required_permission}' "
                f"on document {document_id} (tenant-wide: read-only)"
            )
            raise AuthorizationError(
                f"Access denied: {required_permission} permission required (tenant document is read-only)",
                context={
                    "document_id": document_id,
                    "required_permission": required_permission,
                    "document_visibility": visibility,
                    "user_id": user_id
                }
            )
    
    # Fallback: deny
    raise AuthorizationError(
        "Access denied",
        context={
            "document_id": document_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "visibility": visibility
        }
    )
