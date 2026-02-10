"""
API layer - FastAPI application with endpoints.
Following SOLID: 
- Single Responsibility - Controllers are thin, delegate to services.
- Dependency Inversion - Controllers depend on service abstractions.
"""
import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Confirm execution of main.py
print("main.py is being executed")

# Load environment variables from .env file (check parent directory too)
load_dotenv()
load_dotenv("../.env")
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from prometheus_client import make_asgi_app
from observability.metrics import registry, init_metrics

from domain.models import ChatRequest, ChatResponse, ProfileUpdateRequest
from domain.interfaces import IUserRepository, IConversationRepository
from infrastructure.repositories import FileUserRepository, FileConversationRepository
from infrastructure.tool_clients import (
    RegulationRAGClient,
    GasExportClient,
    MCPClient
)
from services.tools import RegulationTool, GasExportTool
from services.agent import AIAgent
from services.chat_service import ChatService
from services.hybrid_memory.vectorstore import DummyVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
chat_service: ChatService = None
user_repo: IUserRepository = None

regulation_client: RegulationRAGClient = None
gas_export_client: GasExportClient = None
mcp_client: MCPClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initialize services on startup."""
    global chat_service, user_repo, regulation_client, gas_export_client, mcp_client
    
    logger.info("Initializing application...")
    
    # Get OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set!")
        raise RuntimeError("OPENAI_API_KEY must be set")
    
    # Initialize repositories
    user_repo = FileUserRepository(data_dir="data/users")
    conversation_repo = FileConversationRepository(data_dir="data/sessions")

    # Initialize Regulation RAG client
    # Use Docker path if exists, otherwise fallback to local dev path
    pdf_path = "/app/gaztorveny.pdf" if os.path.exists("/app/gaztorveny.pdf") else "backend/data/files/gaztorveny.pdf"
    regulation_client = RegulationRAGClient(
        pdf_path=pdf_path,
        openai_api_key=openai_api_key,
        persist_directory="./chroma_db"
    )
    gas_export_client = GasExportClient()

    # Initialize tools
    regulation_tool = RegulationTool(regulation_client)
    gas_export_tool = GasExportTool(gas_export_client)

    # Initialize agent
    agent = AIAgent(
        openai_api_key=openai_api_key,
        regulation_tool=regulation_tool,
        gas_export_tool=gas_export_tool
    )

    # Initialize chat service with DummyVectorStore for hybrid memory
    vector_store = DummyVectorStore()
    chat_service = ChatService(
        user_repository=user_repo,
        conversation_repository=conversation_repo,
        agent=agent,
        vector_store=vector_store
    )
    
    # Initialize MCP client
    mcp_client = MCPClient()
    
    logger.info("Application initialized successfully")
    
    yield
    
    logger.info("Application shutting down...")


# Initialize metrics with environment and version
init_metrics(environment=os.environ.get("ENVIRONMENT", "dev"), version=os.environ.get("APP_VERSION", "1.1.0"))

# Create FastAPI app
app = FastAPI(
    title="AI Agent Demo (Regulation RAG + Radio tools)",
    description="LangGraph-based AI Agent with tools and memory, including RAG-based regulation Q&A",
    version="1.1.0",
    lifespan=lifespan
)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app(registry=registry)
app.mount("/metrics", metrics_app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



from fastapi import status, Response


# ECS Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(response: Response):
    """ECS health check endpoint."""
    response.status_code = status.HTTP_200_OK
    return {"status": "healthy"}

# ALB health check endpoint (alias)
@app.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz_check(response: Response):
    """ALB health check endpoint alias."""
    response.status_code = status.HTTP_200_OK
    return {"status": "healthy"}

# Root endpoint (optional health/info)
@app.get("/", status_code=status.HTTP_200_OK)
async def root(response: Response):
    response.status_code = status.HTTP_200_OK
    return {"status": "ok", "message": "AI Agent API is running"}


@app.post("/api/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest, response: Response):
    """
    Process chat message.
    
    Handles:
    - Normal chat messages
    - Special 'reset context' command
    - Tool invocations via agent
    - Memory persistence
    """
    try:
        logger.info(f"Chat request from user {request.user_id}")
        chat_resp = await chat_service.process_message(request)
        response.status_code = status.HTTP_200_OK
        return chat_resp
    except TimeoutError:
        logger.error("Chat request timed out")
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Request timed out")
    except ValueError as e:
        logger.error(f"Bad request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/session/{session_id}", status_code=status.HTTP_200_OK)
async def get_session(session_id: str, response: Response):
    """Get conversation history for a session."""
    try:
        history = await chat_service.get_session_history(session_id)
        if not history or not history.get("messages"):
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "Session not found", "session_id": session_id}
        response.status_code = status.HTTP_200_OK
        return history
    except Exception as e:
        logger.error(f"Get session error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/profile/{user_id}", status_code=status.HTTP_200_OK)
async def get_profile(user_id: str, response: Response):
    """Get user profile."""
    try:
        profile = await user_repo.get_profile(user_id)
        if not profile:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "User profile not found", "user_id": user_id}
        response.status_code = status.HTTP_200_OK
        return profile.model_dump(mode='json')
    except Exception as e:
        logger.error(f"Get profile error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.put("/api/profile/{user_id}", status_code=status.HTTP_200_OK)
async def update_profile(user_id: str, request: ProfileUpdateRequest, response: Response):
    """Update user profile."""
    try:
        updates = request.model_dump(exclude_none=True)
        profile = await user_repo.update_profile(user_id, updates)
        response.status_code = status.HTTP_200_OK
        return profile.model_dump(mode='json')
    except ValueError as e:
        logger.error(f"Bad request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Update profile error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/history/search", status_code=status.HTTP_200_OK)
async def search_history(q: str, response: Response):
    """Search across all conversation histories."""
    try:
        results = await chat_service.search_history(q)
        response.status_code = status.HTTP_200_OK
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Search history error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/mcp/tool_call")
async def mcp_tool_call(
    tool_name: str = Body(...),
    arguments: dict = Body(default={})
):
    """Hívj meg egy MCP tool-t név és argumentumok alapján (teszteléshez)."""
    try:
        client = MCPClient()
        await client.connect()
        result = await client.call_tool(tool_name, arguments)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Add logging to confirm app initialization
logger.info("Starting FastAPI application...")

# Ensure the endpoint is registered
logger.info("Registering /test-regulation-tool endpoint")

@app.get("/test-regulation-tool", status_code=status.HTTP_200_OK)
async def test_regulation_tool(response: Response):
    try:
        pdf_path = regulation_client.pdf_path
        if not os.path.exists(pdf_path):
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"success": False, "error": f"PDF file not found at {pdf_path}"}
        # Perform a test query
        result = await regulation_client.query("Test query about the Gas Act")
        response.status_code = status.HTTP_200_OK
        return {"success": True, "result": result}
    except TimeoutError:
        response.status_code = status.HTTP_408_REQUEST_TIMEOUT
        return {"success": False, "error": "Request timed out"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import requests

    try:
        response = requests.get("http://localhost:8000/test-regulation-tool")
        print("Response:", response.json())
    except Exception as e:
        print("Error testing Regulation Tool:", str(e))
