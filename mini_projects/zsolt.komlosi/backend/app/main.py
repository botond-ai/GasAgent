"""
FastAPI application entry point for SupportAI.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import HealthResponse
from app.api.routes import (
    chat_router,
    tickets_router,
    jira_router,
    documents_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    settings = get_settings()
    print(f"Starting SupportAI API on {settings.api_host}:{settings.api_port}")
    print(f"CORS origins: {settings.cors_origins_list}")
    print(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")

    yield

    # Shutdown
    print("Shutting down SupportAI API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="SupportAI API",
        description="Customer Support Triage and Response Agent with RAG Knowledge Base",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(jira_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")

    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint."""
        return {
            "name": "SupportAI API",
            "version": "2.0.0",
            "docs": "/docs",
        }

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health():
        """Health check endpoint."""
        services = {}

        # Check Qdrant connection
        try:
            from app.api.deps import get_qdrant_client
            qdrant = get_qdrant_client()
            qdrant.get_collections()
            services["qdrant"] = "healthy"
        except Exception as e:
            services["qdrant"] = f"unhealthy: {str(e)}"

        # Check Jira configuration
        if settings.jira_configured:
            services["jira"] = "configured"
        else:
            services["jira"] = "not_configured"

        return HealthResponse(
            status="healthy" if services.get("qdrant") == "healthy" else "degraded",
            version="2.0.0",
            services=services,
        )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
