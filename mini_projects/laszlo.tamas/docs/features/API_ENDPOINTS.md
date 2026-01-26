# API Endpoints - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A RESTful API endpoints biztosítják a teljes Knowledge Router funkcionalitás elérését. Minden endpoint multi-tenant és authentikált, Swagger dokumentációval.

## Használat

### Chat endpoint
```bash
# Chat kérés
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Mi a távmunka szabályzat?",
    "user_context": {"tenant_id": 1, "user_id": 1}
  }'
```

### Document processing
```bash
# Dokumentum feltöltés
curl -X POST "http://localhost:8000/api/workflows/document-processing" \
  -F "file=@policy.pdf" \
  -F "tenant_id=1" \
  -F "visibility=tenant"
```

### Memory management
```bash
# Memória létrehozás
curl -X POST "http://localhost:8000/api/memory/" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Alice kedvenc itala a kávé",
    "user_context": {"tenant_id": 1, "user_id": 1}
  }'

# Memória keresés  
curl -X GET "http://localhost:8000/api/memory/search?query=Alice&tenant_id=1&user_id=1"
```

## Technikai implementáció

### API Structure
```
/api/
├── chat/                  # Chat workflow endpoint
├── workflows/
│   └── document-processing # Document upload and processing
├── memory/                # Long-term memory management
│   └── search            # Memory search endpoint
├── health/               # System health checks
└── docs/                 # Swagger UI documentation
```

### FastAPI Route Definitions
```python
# Chat endpoint
@router.post("/chat/")
async def process_chat_query(
    request: ChatRequest,
    db: Session = Depends(get_db)
) -> ChatResponse:
    """Process chat query through unified workflow."""
    
    # Input validation
    validate_chat_request(request)
    
    # Execute workflow
    result = await chat_service.process_chat_query(
        query=request.query,
        tenant_id=request.user_context.tenant_id,
        user_id=request.user_context.user_id,
        session_id=request.session_id
    )
    
    return ChatResponse(
        final_answer=result.final_answer,
        session_id=result.session_id,
        sources_cited=result.sources_cited,
        execution_time_ms=result.total_execution_time_ms
    )

# Document processing endpoint
@router.post("/workflows/document-processing")
async def process_document(
    file: UploadFile = File(...),
    tenant_id: int = Form(...),
    user_id: Optional[int] = Form(None),
    visibility: str = Form("tenant")
) -> DocumentProcessingResponse:
    """Process uploaded document for RAG search."""
    
    # File validation
    validate_uploaded_file(file)
    
    # Process document
    result = await document_processor.process_document(
        file_content=await file.read(),
        filename=file.filename,
        tenant_id=tenant_id,
        user_id=user_id,
        visibility=visibility
    )
    
    return DocumentProcessingResponse(
        document_id=result.document_id,
        chunks_created=result.chunks_created,
        processing_time_ms=result.processing_time_ms
    )
```

### Response Models
```python
from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str
    user_context: UserContext
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    final_answer: str
    session_id: str
    sources_cited: List[Source]
    execution_time_ms: int
    status: str = "success"

class DocumentProcessingResponse(BaseModel):
    document_id: int
    filename: str
    chunks_created: int
    processing_time_ms: int
    status: str = "success"

class MemoryResponse(BaseModel):
    memory_id: int
    content: str
    created_at: str
    embedded: bool
```

## Funkció-specifikus konfiguráció

```ini
# API settings
API_PORT=8000
API_HOST=0.0.0.0
ENABLE_SWAGGER_DOCS=true
MAX_REQUEST_SIZE_MB=50

# CORS settings
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
CORS_ALLOW_CREDENTIALS=true

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
ENABLE_RATE_LIMITING=true
```

### Health Check Endpoint
```python
@router.get("/health/")
async def health_check():
    """System health status."""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": await check_database_health(),
            "vector_store": await check_qdrant_health(), 
            "llm_api": await check_openai_health()
        }
    }
    
    overall_healthy = all(
        service["status"] == "healthy" 
        for service in health_status["services"].values()
    )
    
    health_status["status"] = "healthy" if overall_healthy else "degraded"
    
    return health_status
```