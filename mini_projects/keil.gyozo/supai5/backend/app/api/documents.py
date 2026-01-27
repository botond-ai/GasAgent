"""
Documents API router for knowledge base management.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.core.logging import get_logger
from app.services.document_service import DocumentService
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# Pydantic v2 schemas with ConfigDict
class DocumentMetadata(BaseModel):
    """Document metadata response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc-123",
                "title": "Product FAQ",
                "category": "Product",
                "filename": "faq.pdf",
                "file_type": "pdf",
                "created_at": "2024-01-23T10:30:00Z",
                "chunk_count": 5
            }
        }
    )
    
    id: str = Field(description="Document ID")
    title: str = Field(description="Document title")
    category: str = Field(description="Document category")
    description: str = Field(default="", description="Document description")
    filename: str = Field(description="Original filename")
    file_type: str = Field(description="File extension (pdf, docx, txt, md)")
    created_at: str = Field(description="Creation timestamp in ISO format")
    chunk_count: int = Field(description="Number of chunks processed")


class DocumentStats(BaseModel):
    """Knowledge base statistics."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_documents": 10,
                "total_chunks": 250,
                "categories": {"Product": 5, "Billing": 3, "Technical": 2},
                "collection_status": "ready"
            }
        }
    )
    
    total_documents: int = Field(description="Total number of documents")
    total_chunks: int = Field(description="Total number of chunks")
    categories: dict[str, int] = Field(description="Document count per category")
    collection_status: str = Field(description="Qdrant collection status")


class DocumentUploadResponse(BaseModel):
    """Document upload response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Document uploaded successfully",
                "document": None
            }
        }
    )
    
    success: bool = Field(description="Whether upload succeeded")
    message: str = Field(description="Status message")
    document: Optional[DocumentMetadata] = Field(default=None, description="Uploaded document metadata")


class DocumentDeleteResponse(BaseModel):
    """Document delete response."""
    success: bool = Field(description="Whether deletion succeeded")
    message: str = Field(description="Status message")


class DocumentChunk(BaseModel):
    """Document chunk with text content."""
    chunk_index: int = Field(description="Chunk index within document")
    text: str = Field(description="Chunk text content")


class DocumentDetailResponse(BaseModel):
    """Detailed document response with chunks."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc-123",
                "title": "Product FAQ",
                "category": "Product",
                "description": "FAQ document",
                "filename": "faq.pdf",
                "file_type": "pdf",
                "created_at": "2024-01-23T10:30:00Z",
                "chunk_count": 5,
                "chunks": [{"chunk_index": 0, "text": "Sample text..."}]
            }
        }
    )

    id: str = Field(description="Document ID")
    title: str = Field(description="Document title")
    category: str = Field(description="Document category")
    description: str = Field(default="", description="Document description")
    filename: str = Field(description="Original filename")
    file_type: str = Field(description="File extension")
    created_at: str = Field(description="Creation timestamp")
    chunk_count: int = Field(description="Number of chunks")
    chunks: List[DocumentChunk] = Field(description="Document chunks with text")


# Dependency to get services
async def get_document_service() -> DocumentService:
    """Get document service instance."""
    qdrant_service = QdrantService()
    return DocumentService(qdrant_service)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload and process a document for the knowledge base.

    Supported formats: PDF, DOCX, TXT, MD

    Args:
        file: Document file to upload
        title: Document title
        category: Document category (e.g., Billing, Technical, Product)
        description: Optional document description
        document_service: Injected document service

    Returns:
        Upload response with document metadata
    """
    logger.info(f"Uploading document: {file.filename} ({title})")

    # Validate file type
    allowed_extensions = ['pdf', 'docx', 'txt', 'md']
    file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_extension}. Allowed: {', '.join(allowed_extensions)}"
        )

    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: 10MB"
        )

    try:
        # Process document
        doc_metadata = await document_service.process_document(
            file_content=file_content,
            filename=file.filename,
            title=title,
            category=category,
            description=description
        )

        logger.info(f"Successfully processed document: {doc_metadata['id']}")

        return DocumentUploadResponse(
            success=True,
            message=f"Document '{title}' uploaded and indexed successfully",
            document=DocumentMetadata(**doc_metadata)
        )

    except ValueError as e:
        logger.error(f"Validation error processing document: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )


@router.get("/", response_model=List[DocumentMetadata])
async def list_documents(
    category: Optional[str] = None,
    limit: int = 100,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    List all documents in the knowledge base.

    Args:
        category: Optional category filter
        limit: Maximum number of documents to return (default: 100)
        document_service: Injected document service

    Returns:
        List of document metadata
    """
    try:
        documents = await document_service.list_documents(
            category=category,
            limit=limit
        )

        logger.info(f"Retrieved {len(documents)} documents")
        
        return [DocumentMetadata(**doc) for doc in documents]

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    doc_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Delete a document from the knowledge base.

    Args:
        doc_id: Document ID to delete
        document_service: Injected document service

    Returns:
        Delete response
    """
    logger.info(f"Deleting document: {doc_id}")

    try:
        success = await document_service.delete_document(doc_id)

        if success:
            return DocumentDeleteResponse(
                success=True,
                message=f"Document {doc_id} deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    doc_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get detailed document information including all chunks.

    Args:
        doc_id: Document ID
        document_service: Injected document service

    Returns:
        Document details with all text chunks
    """
    logger.info(f"Fetching document details: {doc_id}")

    try:
        document = await document_service.get_document_with_chunks(doc_id)

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )

        return DocumentDetailResponse(
            id=document["id"],
            title=document["title"],
            category=document["category"],
            description=document.get("description", ""),
            filename=document["filename"],
            file_type=document["file_type"],
            created_at=document["created_at"],
            chunk_count=document["chunk_count"],
            chunks=[
                DocumentChunk(chunk_index=c["chunk_index"], text=c["text"])
                for c in document["chunks"]
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch document: {str(e)}"
        )


@router.get("/stats", response_model=DocumentStats)
async def get_document_stats(
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get knowledge base statistics.

    Args:
        document_service: Injected document service

    Returns:
        Knowledge base statistics
    """
    try:
        stats = await document_service.get_document_stats()
        return DocumentStats(**stats)

    except Exception as e:
        logger.error(f"Error getting document stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )
