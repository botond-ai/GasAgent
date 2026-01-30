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

# Load environment variables from .env file (check parent directory too)
load_dotenv()
load_dotenv("../.env")
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import tempfile
import shutil
import sqlite3

from domain.models import ChatRequest, ChatResponse, ProfileUpdateRequest
from domain.interfaces import IUserRepository, IConversationRepository
from infrastructure.repositories import FileUserRepository, FileConversationRepository
from infrastructure.tool_clients import (
    OpenMeteoWeatherClient, NominatimGeocodeClient, IPAPIGeolocationClient,
    ExchangeRateHostClient, CoinGeckoCryptoClient, RadioBrowserClient,
    DocumentsRAGClient, PCloudClient, SentimentAnalysisClient
)
from infrastructure.smtp_client import SMTPEmailClient
from services.tools import (
    WeatherTool, GeocodeTool, IPGeolocationTool, FXRatesTool, 
    CryptoPriceTool, FileCreationTool, HistorySearchTool, RadioTool,
    DocumentsTool, TranslatorTool, PhotoUploadTool, SentimentTool, JSONCreatorTool,
    SQLiteSaveTool, EmailSendTool, GuardrailsTool
)
from services.agent import AIAgent
from services.chat_service import ChatService
from infrastructure.metrics import (
    PrometheusMiddleware, get_metrics, get_metrics_content_type,
    record_chat_metrics, record_ticket_created, update_ticket_gauges
)
from infrastructure.error_handlers import (
    global_exception_handler, SupportAIException, ValidationException,
    sanitize_user_input, sanitize_filename
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
chat_service: ChatService = None
user_repo: IUserRepository = None
conversation_repo: IConversationRepository = None
templates = Jinja2Templates(directory="templates")

def _is_valid_image(content: bytes, file_ext: str) -> bool:
    """
    Validate image file by checking magic bytes.
    Returns True if content matches expected image format.
    """
    if len(content) < 12:
        return False
    
    # Check magic bytes for common image formats
    magic_bytes = {
        '.jpg': [b'\xFF\xD8\xFF'],
        '.jpeg': [b'\xFF\xD8\xFF'],
        '.png': [b'\x89PNG\r\n\x1a\n'],
        '.gif': [b'GIF87a', b'GIF89a'],
        '.bmp': [b'BM'],
        '.webp': [b'RIFF'],
        '.tiff': [b'II*\x00', b'MM\x00*'],
        '.tif': [b'II*\x00', b'MM\x00*'],
        '.heic': [b'ftyp'],
        '.heif': [b'ftyp'],
    }
    
    # SVG is XML-based, check for XML/SVG markers
    if file_ext == '.svg':
        try:
            content_str = content[:1000].decode('utf-8', errors='ignore').lower()
            return '<svg' in content_str or '<?xml' in content_str
        except:
            return False
    
    expected_signatures = magic_bytes.get(file_ext, [])
    for signature in expected_signatures:
        if content.startswith(signature):
            return True
        # For WEBP, check at offset 8
        if file_ext == '.webp' and len(content) > 12 and content[8:12] == b'WEBP':
            return True
        # For HEIC/HEIF, check at offset 4
        if file_ext in ['.heic', '.heif'] and len(content) > 12 and b'ftyp' in content[4:12]:
            return True
    
    return len(expected_signatures) == 0  # Allow if no signature defined


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initialize services on startup."""
    global chat_service, user_repo
    
    logger.info("Initializing application...")
    
    # Get OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set!")
        raise RuntimeError("OPENAI_API_KEY must be set")
    
    # Initialize repositories
    user_repo = FileUserRepository(data_dir="data/users")
    conversation_repo = FileConversationRepository(data_dir="data/sessions")
    
    # Initialize tool clients
    geocode_client = NominatimGeocodeClient()
    weather_client = OpenMeteoWeatherClient(geocode_client)
    ip_client = IPAPIGeolocationClient()
    fx_client = ExchangeRateHostClient()
    crypto_client = CoinGeckoCryptoClient()
    radio_client = RadioBrowserClient()
    
    # Initialize Documents RAG client
    # Get the absolute path to the Excel files directory
    import pathlib
    backend_dir = pathlib.Path(__file__).parent.absolute()
    # In Docker, the Excel files are mounted at /app/Issue_types_and_details
    # Locally, they're in the parent's parent directory
    docker_docs_path = pathlib.Path("/app/Issue_types_and_details")
    local_docs_path = backend_dir.parent.parent / "Issue_types_and_details"
    documents_path = docker_docs_path if docker_docs_path.exists() else local_docs_path
    
    # Get re-ranker configuration
    reranker_type = os.getenv("RERANKER_TYPE", "llm")  # "cohere" or "llm"
    cohere_api_key = os.getenv("COHERE_API_KEY")
    
    documents_client = DocumentsRAGClient(
        documents_directory=str(documents_path),
        openai_api_key=openai_api_key,
        persist_directory=str(backend_dir / "data" / "documents_vectordb"),
        reranker_type=reranker_type,
        cohere_api_key=cohere_api_key
    )
    logger.info(f"DocumentsRAGClient initialized with re-ranker type: {reranker_type}")
    
    # Initialize tools
    weather_tool = WeatherTool(weather_client)
    geocode_tool = GeocodeTool(geocode_client)
    ip_tool = IPGeolocationTool(ip_client)
    fx_tool = FXRatesTool(fx_client)
    crypto_tool = CryptoPriceTool(crypto_client)
    file_tool = FileCreationTool(data_dir="data/files")
    history_tool = HistorySearchTool(conversation_repo)
    radio_tool = RadioTool(radio_client)
    
    # Initialize translator tool (used by DocumentsTool and available standalone)
    translator_tool = TranslatorTool(openai_api_key=openai_api_key)
    
    # Initialize documents tool with translator for language detection/translation
    documents_tool = DocumentsTool(documents_client, translator_tool=translator_tool)
    
    # Initialize sentiment analysis client and tool
    sentiment_client = SentimentAnalysisClient(openai_api_key=openai_api_key)
    sentiment_tool = SentimentTool(sentiment_client)
    
    # Initialize pCloud client and PhotoUploadTool (optional - only if credentials are provided)
    pcloud_username = os.getenv("PCLOUD_USERNAME")
    pcloud_password = os.getenv("PCLOUD_PASSWORD")
    pcloud_access_token = os.getenv("PCLOUD_ACCESS_TOKEN")
    pcloud_endpoint = os.getenv("PCLOUD_ENDPOINT", "eapi")  # 'eapi' for Europe, 'api' for US
    tickets_folder_id = os.getenv("PCLOUD_TICKETS_FOLDER_ID")
    photo_upload_tool = None
    
    if pcloud_username and pcloud_password:
        try:
            pcloud_client = PCloudClient(
                username=pcloud_username,
                password=pcloud_password,
                photo_memories_folder_id=int(tickets_folder_id) if tickets_folder_id else None,
                endpoint=pcloud_endpoint
            )
            photo_upload_tool = PhotoUploadTool(
                cloud_client=pcloud_client,
                tickets_folder_id=int(tickets_folder_id) if tickets_folder_id else None
            )
            logger.info("pCloud client and PhotoUploadTool initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize pCloud client: {e}. Photo upload will be disabled.")
    elif pcloud_access_token:
        try:
            pcloud_client = PCloudClient(
                access_token=pcloud_access_token,
                photo_memories_folder_id=int(tickets_folder_id) if tickets_folder_id else None,
                endpoint=pcloud_endpoint
            )
            photo_upload_tool = PhotoUploadTool(
                cloud_client=pcloud_client,
                tickets_folder_id=int(tickets_folder_id) if tickets_folder_id else None
            )
            logger.info("pCloud client (OAuth) and PhotoUploadTool initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize pCloud client: {e}. Photo upload will be disabled.")
    else:
        logger.info("PCLOUD_USERNAME/PCLOUD_PASSWORD or PCLOUD_ACCESS_TOKEN not set. Photo upload tool will be disabled.")
    
    # Initialize JSON creator tool
    json_creator_tool = JSONCreatorTool(data_dir="data/tickets")
    logger.info("JSONCreatorTool initialized")
    
    # Initialize Guardrails tool for PII masking and legal compliance
    guardrails_tool = GuardrailsTool()
    logger.info("GuardrailsTool initialized")
    
    # Initialize SQLite save tool
    sqlite_save_tool = SQLiteSaveTool()
    logger.info("SQLiteSaveTool initialized")
    
    # Initialize SMTP email client and EmailSendTool
    gmail_username = os.getenv("GMAIL_USERNAME")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
    gmail_smtp_server = os.getenv("GMAIL_SMTP_SERVER", "smtp.gmail.com")
    gmail_smtp_port = int(os.getenv("GMAIL_SMTP_PORT", "587"))
    gmail_to_email = os.getenv("GMAIL_TO_EMAIL")
    email_send_tool = None
    
    if gmail_username and gmail_app_password and gmail_to_email:
        try:
            smtp_client = SMTPEmailClient(
                username=gmail_username,
                app_password=gmail_app_password,
                smtp_server=gmail_smtp_server,
                smtp_port=gmail_smtp_port
            )
            email_send_tool = EmailSendTool(
                email_client=smtp_client,
                from_email=gmail_username,
                to_email=gmail_to_email
            )
            logger.info("SMTP email client and EmailSendTool initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize SMTP email client: {e}. Email notifications will be disabled.")
    else:
        logger.info("Gmail SMTP credentials not set. Email notifications will be disabled.")
    
    # Initialize agent
    agent = AIAgent(
        openai_api_key=openai_api_key,
        weather_tool=weather_tool,
        geocode_tool=geocode_tool,
        ip_tool=ip_tool,
        fx_tool=fx_tool,
        crypto_tool=crypto_tool,
        file_tool=file_tool,
        history_tool=history_tool,
        radio_tool=radio_tool,
        documents_tool=documents_tool,
        translator_tool=translator_tool,
        photo_upload_tool=photo_upload_tool,
        sentiment_tool=sentiment_tool,
        json_creator_tool=json_creator_tool,
        guardrails_tool=guardrails_tool,
        sqlite_save_tool=sqlite_save_tool,
        email_send_tool=email_send_tool
    )
    
    # Initialize chat service
    chat_service = ChatService(
        user_repository=user_repo,
        conversation_repository=conversation_repo,
        agent=agent
    )
    
    logger.info("Application initialized successfully")
    
    yield
    
    logger.info("Application shutting down...")


# Create FastAPI app
app = FastAPI(
    title="SupportAI Agent (Documents RAG + Radio tools)",
    description="LangGraph-based AI Agent with tools and memory, including RAG-based book Q&A",
    version="1.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics middleware
app.add_middleware(PrometheusMiddleware)

# Register global exception handlers
@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    return await global_exception_handler(request, exc)

@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent format."""
    return await global_exception_handler(request, exc)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "AI Agent API is running"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process chat message.
    
    Handles:
    - Normal chat messages
    - Special 'reset context' command
    - Tool invocations via agent
    - Memory persistence
    """
    try:
        # Validate and sanitize input
        if not request.user_id or not request.user_id.strip():
            raise HTTPException(status_code=400, detail="user_id is required")
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="message is required")
        
        # Sanitize user input
        request.message = sanitize_user_input(request.message, max_length=50000)
        
        logger.info(f"Chat request from user {request.user_id}")
        response = await chat_service.process_message(request)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)[:200]}")


@app.post("/api/chat/upload", response_model=ChatResponse)
async def chat_with_files(
    user_id: str = Form(...),
    message: str = Form(...),
    session_id: str = Form(None),
    files: List[UploadFile] = File(default=[])
):
    """
    Process chat message with file uploads.
    
    Handles:
    - Chat messages with attached files
    - Files are saved temporarily and passed to the photo_upload tool
    - Supports multiple file uploads via drag-and-drop or file picker
    - Validates file types, sizes, and content
    """
    temp_dir = None
    
    # File validation constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
    MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200MB total
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif', '.tiff', '.tif', '.svg'}
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
        'image/heic', 'image/heif', 'image/tiff', 'image/svg+xml'
    }
    
    try:
        # Validate and sanitize input
        if not user_id or not user_id.strip():
            raise HTTPException(status_code=400, detail="user_id is required")
        if not message or not message.strip():
            raise HTTPException(status_code=400, detail="message is required")
        
        # Sanitize user input
        message = sanitize_user_input(message, max_length=50000)
        
        logger.info(f"Chat with files request from user {user_id}, {len(files)} files attached")
        
        # Validate number of files
        if len(files) > 50:
            raise HTTPException(status_code=400, detail="Too many files. Maximum 50 files per upload.")
        
        # Check available disk space
        import shutil as shutil_disk
        stat = shutil_disk.disk_usage(tempfile.gettempdir())
        available_space = stat.free
        if available_space < 500 * 1024 * 1024:  # Less than 500MB available
            logger.error(f"Low disk space: {available_space / (1024*1024):.1f} MB available")
            raise HTTPException(status_code=507, detail="Insufficient disk space on server")
        
        # Save uploaded files to temporary directory with validation
        file_paths = []
        file_names = []
        total_size = 0
        validation_errors = []
        
        if files:
            temp_dir = tempfile.mkdtemp()
            for idx, file in enumerate(files):
                if not file.filename:
                    continue
                
                # Validate file extension
                file_ext = os.path.splitext(file.filename)[1].lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    validation_errors.append(f"{file.filename}: Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
                    continue
                
                # Validate MIME type
                if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
                    validation_errors.append(f"{file.filename}: Invalid MIME type '{file.content_type}'")
                    continue
                
                # Read file content
                content = await file.read()
                file_size = len(content)
                
                # Validate file size
                if file_size == 0:
                    validation_errors.append(f"{file.filename}: File is empty")
                    continue
                
                if file_size > MAX_FILE_SIZE:
                    size_mb = file_size / (1024 * 1024)
                    validation_errors.append(f"{file.filename}: File too large ({size_mb:.1f}MB). Maximum {MAX_FILE_SIZE/(1024*1024):.0f}MB per file")
                    continue
                
                total_size += file_size
                if total_size > MAX_TOTAL_SIZE:
                    validation_errors.append(f"Total upload size exceeds {MAX_TOTAL_SIZE/(1024*1024):.0f}MB limit")
                    break
                
                # Validate file magic bytes (basic image validation)
                if not _is_valid_image(content, file_ext):
                    validation_errors.append(f"{file.filename}: File content doesn't match image format")
                    continue
                
                # Save file
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as buffer:
                    buffer.write(content)
                
                file_paths.append(file_path)
                file_names.append(file.filename)
                logger.info(f"Saved and validated file: {file.filename} ({file_size/1024:.1f} KB)")
        
        # If all files failed validation, return error
        if validation_errors and not file_paths:
            error_msg = "All files failed validation:\n" + "\n".join(validation_errors)
            logger.warning(f"File validation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Log validation warnings if some files were rejected
        if validation_errors:
            logger.warning(f"Some files rejected: {validation_errors}")
        
        # Create chat request with file info in message
        file_info = ""
        if file_names:
            file_info = f"\n\n[ATTACHED FILES: {', '.join(file_names)}]"
        
        # Store file info in a way the agent can access
        enhanced_message = message + file_info
        
        # Create the request
        request = ChatRequest(
            user_id=user_id,
            message=enhanced_message,
            session_id=session_id
        )
        
        # Process message - pass file paths to chat service
        response = await chat_service.process_message_with_files(
            request, 
            file_paths=file_paths,
            file_names=file_names
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat with files error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        # Clean up temporary files
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get conversation history for a session."""
    try:
        history = await chat_service.get_session_history(session_id)
        return history
    except Exception as e:
        logger.error(f"Get session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str):
    """Get user profile."""
    try:
        profile = await user_repo.get_profile(user_id)
        return profile.model_dump(mode='json')
    except Exception as e:
        logger.error(f"Get profile error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/profile/{user_id}")
async def update_profile(user_id: str, request: ProfileUpdateRequest):
    """Update user profile."""
    try:
        updates = request.model_dump(exclude_none=True)
        profile = await user_repo.update_profile(user_id, updates)
        return profile.model_dump(mode='json')
    except Exception as e:
        logger.error(f"Update profile error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/search")
async def search_history(q: str):
    """Search across all conversation histories."""
    try:
        results = await chat_service.search_history(q)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Search history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tickets", response_class=HTMLResponse)
async def tickets_page(request: Request):
    """Serve the tickets dashboard page."""
    return templates.TemplateResponse("tickets.html", {"request": request})


@app.get("/api/tickets/count")
async def get_tickets_count():
    """Get total count of tickets."""
    try:
        db_path = "data/tickets.db"
        if not os.path.exists(db_path):
            return {"total": 0}
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets")
        count = cursor.fetchone()[0]
        conn.close()
        
        return {"total": count}
    except Exception as e:
        logger.error(f"Get tickets count error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickets/filter")
async def filter_tickets(
    ticket_number: str = "",
    user_name: str = "",
    sentiment: str = "",
    contact_time: str = "",
    issue_type: str = "",
    potential_issue: str = "",
    owning_team: str = "",
    priority: str = ""
):
    """Filter tickets based on provided criteria with real-time search."""
    try:
        db_path = "data/tickets.db"
        if not os.path.exists(db_path):
            return HTMLResponse(content='<div class="no-results">No tickets database found.</div>')
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build dynamic query
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []
        
        if ticket_number:
            query += " AND ticket_number LIKE ?"
            params.append(f"%{ticket_number}%")
        
        if user_name:
            query += " AND user_name LIKE ?"
            params.append(f"%{user_name}%")
        
        if sentiment:
            query += " AND sentiment LIKE ?"
            params.append(f"%{sentiment}%")
        
        if contact_time:
            # Convert YYYY.MM.DD to YYYY-MM-DD for SQLite date comparison
            try:
                year, month, day = contact_time.split('.')
                formatted_date = f"{year}-{month}-{day}"
                query += " AND DATE(contact_time) = ?"
                params.append(formatted_date)
            except ValueError:
                # If format is invalid, skip the filter
                pass
        
        if issue_type:
            query += " AND issue_type LIKE ?"
            params.append(f"%{issue_type}%")
        
        if potential_issue:
            query += " AND potential_issue LIKE ?"
            params.append(f"%{potential_issue}%")
        
        if owning_team:
            query += " AND owning_team LIKE ?"
            params.append(f"%{owning_team}%")
        
        if priority:
            query += " AND priority LIKE ?"
            params.append(f"%{priority}%")
        
        query += " ORDER BY created_at DESC LIMIT 1000"
        
        cursor.execute(query, params)
        tickets = cursor.fetchall()
        conn.close()
        
        # Build HTML table
        if not tickets:
            return HTMLResponse(content='<div class="no-results">No tickets found matching your filters.</div>')
        
        html = '<table><thead><tr>'
        html += '<th>Ticket #</th>'
        html += '<th>User Name</th>'
        html += '<th>Sentiment</th>'
        html += '<th>Contact Time</th>'
        html += '<th>Issue Type</th>'
        html += '<th>Potential Issue</th>'
        html += '<th>Owning Team</th>'
        html += '<th>Priority</th>'
        html += '</tr></thead><tbody>'
        
        for ticket in tickets:
            html += '<tr>'
            html += f'<td>{ticket["ticket_number"] or "N/A"}</td>'
            html += f'<td>{ticket["user_name"] or "N/A"}</td>'
            
            # Sentiment with badge
            sentiment_val = ticket["sentiment"] or "neutral"
            sentiment_class = f"sentiment-{sentiment_val.lower()}"
            html += f'<td><span class="sentiment-badge {sentiment_class}">{sentiment_val}</span></td>'
            
            html += f'<td>{ticket["contact_time"] or "N/A"}</td>'
            html += f'<td>{ticket["issue_type"] or "N/A"}</td>'
            html += f'<td>{ticket["potential_issue"] or "N/A"}</td>'
            html += f'<td>{ticket["owning_team"] or "N/A"}</td>'
            
            # Priority with badge
            priority_val = ticket["priority"] or "P3"
            priority_class = f"priority-{priority_val}"
            html += f'<td><span class="priority-badge {priority_class}">{priority_val}</span></td>'
            
            html += '</tr>'
        
        html += '</tbody></table>'
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        logger.error(f"Filter tickets error: {e}", exc_info=True)
        return HTMLResponse(content=f'<div class="no-results">Error loading tickets: {str(e)}</div>')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
