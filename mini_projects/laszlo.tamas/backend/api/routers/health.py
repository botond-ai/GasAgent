"""
Health & System Endpoints

Provides health checks, version info, and database connection status.
No authentication required - used for monitoring and load balancer health checks.
"""

import logging
from fastapi import APIRouter
from database.pg_connection import check_db_connection

logger = logging.getLogger(__name__)

router = APIRouter()

# Read version from environment or config
from config.config_service import get_config_value

def get_app_version() -> str:
    """Read APP_VERSION from system.ini."""
    try:
        return get_config_value("application", "APP_VERSION", "0.0.0")
    except Exception as e:
        logger.warning(f"Failed to load APP_VERSION: {e}")
        return "0.0.0"

APP_VERSION = get_app_version()


@router.get("/")
async def root():
    """
    Root endpoint - basic health check.
    
    Returns:
        {"status": "ok", "message": "...", "version": "x.x.x"}
    """
    return {
        "status": "ok",
        "message": f"Knowledge Router - PROD {APP_VERSION} API",
        "version": APP_VERSION
    }


@router.get("/health")
async def health():
    """
    Health check endpoint for load balancers.
    
    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


@router.get("/api/version")
async def get_version():
    """
    Get application version.
    
    Returns:
        {"version": "x.x.x", "name": "..."}
    """
    return {
        "version": APP_VERSION,
        "name": f"Knowledge Router - PROD {APP_VERSION}"
    }


@router.get("/api/db-check")
async def db_check():
    """
    Check PostgreSQL database connection.
    
    Returns:
        {"status": "connected", "database": "..."} on success
        {"status": "error", "error": "..."} on failure
    """
    try:
        db_status = check_db_connection()
        return db_status
    except Exception as e:
        logger.error(f"Database check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
