"""
FastAPI application entry point - UPDATED with Documents router
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import get_logger
from app.api.tickets import router as tickets_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)

app = FastAPI(
    title="SupportAI API",
    description="AI-powered customer support triage and response system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(tickets_router, prefix="/api/tickets", tags=["tickets"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(documents_router)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting SupportAI application")
    
    # Initialize Qdrant collection
    qdrant = QdrantService()
    await qdrant.ensure_collection()
    
    logger.info("Qdrant collection initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down SupportAI application")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "SupportAI API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}