"""
Test endpoint for structured JSON logging validation.

Tests:
1. JSON format output
2. Correlation ID injection (request_id, tenant_id, user_id)
3. Loki batch shipping
"""
import logging
from fastapi import APIRouter, Request
from api.middleware.request_context import (
    request_id_ctx_var,
    tenant_id_ctx_var,
    user_id_ctx_var,
    set_request_context,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/test-logging")
async def test_logging(request: Request):
    """
    Test structured JSON logging with correlation IDs.
    
    Expected log output:
    {
        "timestamp": "2026-01-17T...",
        "level": "INFO",
        "message": "Test log message",
        "request_id": "...",
        "tenant_id": 1,
        "user_id": 1
    }
    """
    # Simulate request context setup
    set_request_context(
        request_id="test-req-abc-123",
        session_id="test-session-xyz",
        tenant_id=1,
        user_id=1,
    )
    
    # Log with correlation IDs automatically injected
    logger.info("✅ Test log message from /test-logging endpoint")
    logger.warning("⚠️ Test warning with correlation ID injection")
    logger.error("❌ Test error for Loki aggregation")
    
    # Verify ContextVars are set
    return {
        "status": "success",
        "message": "Logged 3 messages with correlation IDs",
        "context": {
            "request_id": request_id_ctx_var.get(),
            "tenant_id": tenant_id_ctx_var.get(),
            "user_id": user_id_ctx_var.get(),
        }
    }
