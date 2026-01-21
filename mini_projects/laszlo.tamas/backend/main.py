import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# SOLID-compliant router registration
from api.registry import get_router_registry
from api.dependencies import init_workflows
from api.websocket_endpoints import router as websocket_router
from api.exception_middleware import register_exception_handlers
from database.pg_init import init_postgres_schema, seed_database, seed_documents

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_format = os.getenv("LOG_FORMAT", "text").lower()  # "json" or "text"
loki_url = os.getenv("LOKI_URL", "")

# Force UTF-8 for stdout/stderr (Windows compatibility)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configure logging format based on LOG_FORMAT
handlers = []

if log_format == "json":
    # JSON logging with Loki integration
    from observability.structured_logger import JSONFormatter
    from observability.loki_handler import create_loki_handler
    
    # Console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    handlers.append(console_handler)
    
    # Loki handler (if configured)
    if loki_url:
        loki_handler = create_loki_handler(
            loki_url=loki_url,
            job_name="knowledge-router-backend",
            batch_size=100,
            flush_interval=5.0,
        )
        if loki_handler:
            loki_handler.setFormatter(JSONFormatter())
            handlers.append(loki_handler)
else:
    # Text logging (default)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    handlers.append(console_handler)

logging.basicConfig(
    level=getattr(logging, log_level),
    handlers=handlers,
    force=True,
)

# Suppress health check logs from Uvicorn access log
class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        return "/health" not in getattr(record, 'getMessage', lambda: '')()

# Apply filter to Uvicorn access logger
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(HealthCheckFilter())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle: startup and shutdown.
    
    Startup sequence:
    1. Initialize PostgreSQL schema
    2. Initialize LangGraph workflows
    3. Initialize OpenTelemetry tracing
    """
    logger.info("🚀 Starting application...")
    
    # Step 1: Initialize PostgreSQL schema
    logger.info("🔄 Initializing PostgreSQL schema...")
    init_postgres_schema()
    logger.info("✅ PostgreSQL schema initialized")
    
    # Step 2: Seed database with initial data
    logger.info("🌱 Seeding database...")
    seed_database()
    logger.info("✅ Database seeding complete")
    
    # Step 3: Seed documents with full processing (chunk + embed + Qdrant)
    logger.info("📄 Seeding test documents...")
    await seed_documents()
    logger.info("✅ Document seeding complete")
    
    # Step 4: Initialize workflows (UnifiedChatWorkflow)
    logger.info("🔄 Initializing LangGraph workflows...")
    init_workflows()
    logger.info("✅ Workflows initialized")
    
    # Step 5: Initialize OpenTelemetry tracing
    logger.info("📊 Initializing observability...")
    from observability import init_tracing
    init_tracing()
    
    yield
    
    logger.info("🛑 Shutting down application...")


# Load version from system.ini
def get_app_version() -> str:
    """Read APP_VERSION from system.ini."""
    try:
        from config.config_service import get_config_value
        return get_config_value("application", "APP_VERSION", "0.0.0")
    except Exception as e:
        logger.warning(f"Failed to load APP_VERSION from system.ini: {e}")
        return "0.0.0"

APP_VERSION = get_app_version()

# Initialize rate limiter (reads from system.ini [rate_limiting])
from config.settings import REQUESTS_PER_MINUTE
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{REQUESTS_PER_MINUTE}/minute"])

app = FastAPI(
    title=f"Knowledge Router - PROD {APP_VERSION}",
    description="Multi-tenant RAG Chat System with LangGraph, Document Management, and Long-Term Memory",
    version=APP_VERSION,
    lifespan=lifespan,
    default_response_class=JSONResponse  # Standard JSON with UTF-8 support
)

# Attach limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register exception handlers (must be before CORS middleware)
register_exception_handlers(app)

# ===== OBSERVABILITY MIDDLEWARE (Order matters: last registered = first executed) =====
#
# Middleware execution order (request flow):
# 1. TracingMiddleware (outermost - creates root span)
# 2. RequestContextMiddleware (injects request_id, extracts trace_id)
# 3. CORSMiddleware
# 4. ... route handlers ...
#
from api.middleware import RequestContextMiddleware, TracingMiddleware

# Add tracing middleware (outermost - creates root OTEL span)
app.add_middleware(TracingMiddleware)

# Add request context middleware (injects correlation IDs)
app.add_middleware(RequestContextMiddleware)

# Configure CORS - Local development only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== ROUTER REGISTRATION (SOLID - Open/Closed Principle) =====
# 
# New routers are added via api/registry.py, not here.
# This follows the Open/Closed principle: adding domains doesn't modify main.py.
#
# Registry returns: List[(APIRouter, config_dict)]
# Config dict: {"prefix": "/api/tenants", "tags": ["tenants"]}
#
logger.info("📡 Registering API routers...")
for router, config in get_router_registry():
    app.include_router(router, **config)
    logger.info(f"  ✅ {config.get('prefix', '/')} - {config.get('tags', [])}")

# WebSocket router (not in registry - special handling)
app.include_router(websocket_router)
