# API Reference - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A komplet REST API dokumentáció minden endpoint-hoz. OpenAPI 3.0 specifikáció alapján automatikusan generált Swagger UI és programmatikus API kliens támogatás.

## Használat

### API dokumentáció elérése
```
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
```

### API kliens generálás
```bash
# Python kliens generálás
openapi-generator generate \
  -i http://localhost:8000/openapi.json \
  -g python \
  -o ./client/python

# TypeScript kliens
openapi-generator generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-axios \
  -o ./client/typescript
```

### API key authentication
```bash
# Header-based auth
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json"
```

## Technikai implementáció

### Core API Endpoints

#### Chat Workflow
```python
@router.post("/api/chat/", response_model=ChatResponse)
async def process_chat_query(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
) -> ChatResponse:
    """
    Process chat query through unified workflow.
    
    Args:
        request: Chat query with user context
        current_user: Authenticated user information
        
    Returns:
        ChatResponse with final answer and metadata
        
    Raises:
        HTTPException: 400 for invalid input, 500 for processing errors
    """
    
    validate_chat_request(request)
    
    try:
        result = await chat_service.process_chat_query(
            query=request.query,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            session_id=request.session_id
        )
        
        return ChatResponse(
            final_answer=result.final_answer,
            session_id=result.session_id,
            sources_cited=result.sources_cited,
            execution_time_ms=result.total_execution_time_ms,
            workflow_steps=result.execution_steps
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

#### Document Processing
```python
@router.post("/api/workflows/document-processing", response_model=DocumentProcessingResponse)
async def process_document(
    file: UploadFile = File(..., description="Document file to process"),
    visibility: str = Form("tenant", description="Document visibility: 'tenant' or 'user'"),
    current_user: User = Depends(get_current_user)
) -> DocumentProcessingResponse:
    """
    Process uploaded document for RAG search.
    
    Supported formats: PDF, DOCX, TXT
    Max file size: 50MB
    
    Args:
        file: Document file upload
        visibility: Access level ('tenant' or 'user')
        current_user: Authenticated user
        
    Returns:
        Processing result with document ID and chunk count
    """
    
    # File validation
    validate_uploaded_file(file)
    
    try:
        file_content = await file.read()
        
        result = await document_processor.process_document(
            file_content=file_content,
            filename=file.filename,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            visibility=visibility
        )
        
        return DocumentProcessingResponse(
            document_id=result.document_id,
            filename=file.filename,
            chunks_created=result.chunks_created,
            processing_time_ms=result.processing_time_ms,
            embeddings_generated=result.embeddings_generated
        )
        
    except FileTooLargeError:
        raise HTTPException(status_code=413, detail="File too large")
    except UnsupportedFileTypeError:
        raise HTTPException(status_code=415, detail="Unsupported file type")
```

#### Memory Management
```python
@router.post("/api/memory/", response_model=MemoryResponse)
async def create_memory(
    request: CreateMemoryRequest,
    current_user: User = Depends(get_current_user)
) -> MemoryResponse:
    """
    Create long-term memory for user.
    
    Args:
        request: Memory content and metadata
        current_user: Authenticated user
        
    Returns:
        Created memory with ID and embedding status
    """
    
    memory = await memory_service.create_long_term_memory(
        content=request.content,
        memory_type=request.memory_type or "explicit_fact",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        metadata=request.metadata
    )
    
    return MemoryResponse.from_orm(memory)

@router.get("/api/memory/search", response_model=List[MemoryResponse])
async def search_memories(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    current_user: User = Depends(get_current_user)
) -> List[MemoryResponse]:
    """
    Search user's long-term memories.
    
    Args:
        query: Semantic search query
        limit: Maximum number of results
        memory_type: Optional memory type filter
        current_user: Authenticated user
        
    Returns:
        List of matching memories with relevance scores
    """
    
    memories = await memory_service.search_memories(
        query=query,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        limit=limit,
        memory_type=memory_type
    )
    
    return [MemoryResponse.from_orm(memory) for memory in memories]
```

### Request/Response Models
```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    """Chat query request model."""
    
    query: str = Field(..., description="User query", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="Optional session ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Mi a távmunka szabályzat?",
                "session_id": "uuid-v4-string",
                "context": {"urgent": True}
            }
        }

class ChatResponse(BaseModel):
    """Chat query response model."""
    
    final_answer: str = Field(..., description="Generated response")
    session_id: str = Field(..., description="Session identifier")
    sources_cited: List[Source] = Field(default_factory=list, description="Referenced documents")
    execution_time_ms: int = Field(..., description="Processing time in milliseconds")
    workflow_steps: List[WorkflowStep] = Field(default_factory=list, description="Execution steps")
    
    class Config:
        schema_extra = {
            "example": {
                "final_answer": "A távmunka szabályzat szerint...",
                "session_id": "abc123-def456",
                "sources_cited": [
                    {
                        "document_id": 123,
                        "filename": "policy.pdf",
                        "page": 5,
                        "relevance_score": 0.95
                    }
                ],
                "execution_time_ms": 2450,
                "workflow_steps": [
                    {
                        "node_name": "reasoning",
                        "duration_ms": 850,
                        "status": "completed"
                    }
                ]
            }
        }

class DocumentProcessingRequest(BaseModel):
    """Document processing request (form data)."""
    pass  # Handled via FastAPI File() and Form()

class DocumentProcessingResponse(BaseModel):
    """Document processing response model."""
    
    document_id: int = Field(..., description="Created document ID")
    filename: str = Field(..., description="Original filename")
    chunks_created: int = Field(..., description="Number of text chunks")
    processing_time_ms: int = Field(..., description="Processing time")
    embeddings_generated: bool = Field(..., description="Whether embeddings were created")
    
class CreateMemoryRequest(BaseModel):
    """Create memory request model."""
    
    content: str = Field(..., description="Memory content", min_length=1, max_length=5000)
    memory_type: Optional[str] = Field("explicit_fact", description="Memory type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('memory_type')
    def validate_memory_type(cls, v):
        allowed_types = ['explicit_fact', 'session_summary', 'preference']
        if v and v not in allowed_types:
            raise ValueError(f'memory_type must be one of: {allowed_types}')
        return v

class MemoryResponse(BaseModel):
    """Memory response model."""
    
    id: int
    content: str
    memory_type: str
    created_at: datetime
    updated_at: datetime
    relevance_score: Optional[float] = None
    
    class Config:
        from_attributes = True
```

### Error Handling
```python
from fastapi import HTTPException, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

class APIException(Exception):
    """Base API exception."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code

class ValidationException(APIException):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)

class AuthenticationException(APIException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)

class AuthorizationException(APIException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)

@app.exception_handler(APIException)
async def api_exception_handler(request, exc: APIException):
    """Custom API exception handler."""
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": type(exc).__name__,
                "status_code": exc.status_code
            },
            "request_id": getattr(request.state, 'request_id', None)
        }
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    """Pydantic validation error handler."""
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation error",
                "details": exc.errors()
            }
        }
    )
```

## Funkció-specifikus konfiguráció

```ini
# API settings
API_TITLE=Knowledge Router API
API_VERSION=1.0.0
API_DESCRIPTION=Multi-tenant RAG knowledge routing system
DOCS_URL=/docs
REDOC_URL=/redoc

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOWED_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOWED_HEADERS=*

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=20

# File upload
MAX_UPLOAD_SIZE_BYTES=52428800  # 50MB
ALLOWED_FILE_TYPES=pdf,docx,txt
```

### OpenAPI Configuration
```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    """Custom OpenAPI schema generation."""
    
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title="Knowledge Router API",
        version="1.0.0",
        description="""
        Multi-tenant RAG (Retrieval-Augmented Generation) knowledge routing system.
        
        ## Features
        - Multi-tenant document processing
        - Intelligent chat workflows
        - Long-term memory management  
        - Semantic search capabilities
        - Session-based conversations
        
        ## Authentication
        All endpoints require API key authentication via Authorization header.
        """,
        routes=app.routes,
        servers=[
            {"url": "http://localhost:8000", "description": "Development"},
            {"url": "https://api.knowledge-router.com", "description": "Production"}
        ]
    )
    
    # Custom security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization"
        }
    }
    
    # Apply security to all endpoints
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"ApiKeyAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```