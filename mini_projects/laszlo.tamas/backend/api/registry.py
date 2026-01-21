"""
API Router Registry - Open/Closed Principle

Central registry for all API routers. Adding new domains doesn't modify existing code.
Each router is registered with its prefix and tags for automatic OpenAPI documentation.
"""

from typing import List, Tuple, Dict, Any
from fastapi import APIRouter


def get_router_registry() -> List[Tuple[APIRouter, Dict[str, Any]]]:
    """
    Get all API routers with their configuration.
    
    Returns:
        List of (router, config) tuples where config contains:
        - prefix: URL prefix for the router
        - tags: OpenAPI tags for documentation grouping
    
    Usage in main.py:
        for router, config in get_router_registry():
            app.include_router(router, **config)
    """
    # Import routers lazily to avoid circular dependencies
    from api.routers import (
        health,
        tenants,
        users,
        sessions,
        documents,
        chat,
        workflows,
        workflow_endpoints,  # PHASE 3: Workflow tracking API
        warmup,
        admin,
        debug,
        admin_routes,  # Runtime-configurable tracking
        monitoring,    # Prometheus metrics
        test_logging,  # JSON logging validation
        excel,  # Excel file downloads
    )
    
    return [
        # Health & System (no /api prefix)
        (health.router, {"tags": ["Health & System"]}),
        
        # Observability
        (monitoring.router, {"tags": ["Monitoring"]}),  # /metrics endpoint
        (test_logging.router, {"prefix": "/api/test", "tags": ["Testing"]}),  # JSON logging test
        
        # Core Resources (RESTful)
        (tenants.router, {"prefix": "/api/tenants", "tags": ["Tenants"]}),
        (users.router, {"prefix": "/api/users", "tags": ["Users"]}),
        (sessions.router, {"prefix": "/api/sessions", "tags": ["Sessions"]}),
        (documents.router, {"prefix": "/api/documents", "tags": ["Documents"]}),
        (excel.router, {"prefix": "/api/excel", "tags": ["Excel"]}),  # Excel file downloads
        
        # Business Logic
        (chat.router, {"prefix": "/api/chat", "tags": ["Chat"]}),
        (workflows.router, {"prefix": "/api/workflows", "tags": ["Workflows"]}),
        (workflow_endpoints.router, {"prefix": "/api", "tags": ["Workflow Tracking"]}),  # PHASE 3: Execution history
        (warmup.router, {"prefix": "/api/cache", "tags": ["Performance"]}),
        
        # Administration
        (admin.router, {"prefix": "/api/admin", "tags": ["Admin"]}),
        (admin_routes.router, {"tags": ["Admin Config"]}),  # Already has /api/admin prefix
        (debug.router, {"prefix": "/api/debug", "tags": ["Debug"]}),
    ]
