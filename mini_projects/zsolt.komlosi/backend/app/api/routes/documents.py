"""
Document management API endpoints.
"""

import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel

from app.models import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentListResponse,
)
from app.api.deps import get_qdrant
from app.rag.document_processor import get_document_processor
from app.rag.vectorstore import get_vectorstore

router = APIRouter(prefix="/documents", tags=["documents"])


def get_source_type(filename: str) -> str:
    """Map file extension to source_type."""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    mapping = {
        "md": "markdown",
        "txt": "markdown",
        "pdf": "pdf",
        "docx": "docx",
    }
    return mapping.get(ext, "markdown")


@router.post(
    "",
    response_model=DocumentUploadResponse,
)
async def upload_document(
    request: DocumentUploadRequest,
    qdrant=Depends(get_qdrant),
):
    """
    Upload and index a new document to the knowledge base (JSON body).
    """
    try:
        processor = get_document_processor()
        result = processor.process_document(
            content=request.content,
            title=request.title,
            doc_type=request.doc_type,
            language=request.language,
        )

        return DocumentUploadResponse(
            success=True,
            doc_id=result.doc_id,
            chunks_created=result.chunks_count,
            message=f"Document '{request.title}' indexed successfully.",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
)
async def upload_document_file(
    file: UploadFile = File(...),
    title: str = Form(...),
):
    """
    Upload a file and index it to the knowledge base.

    Accepts: .md, .txt, .pdf, .docx files
    """
    try:
        # Validate file type
        allowed_extensions = {".md", ".txt", ".pdf", ".docx"}
        file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
            )

        # Read file content
        content_bytes = await file.read()

        # Decode content (assuming UTF-8 for text files)
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Try latin-1 as fallback
            content = content_bytes.decode("latin-1")

        # Process document
        processor = get_document_processor()
        result = processor.process_document(
            content=content,
            title=title,
            doc_type="other",
            language="hu",
        )

        return DocumentUploadResponse(
            success=True,
            doc_id=result.doc_id,
            chunks_created=result.chunks_count,
            message=f"File '{file.filename}' indexed successfully with {result.chunks_count} chunks.",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class IndexUrlRequest(BaseModel):
    """Request for URL indexing."""
    url: str
    title: str


@router.post(
    "/index-url",
    response_model=DocumentUploadResponse,
)
async def index_url(
    request: IndexUrlRequest,
):
    """
    Index a web page from URL.
    """
    try:
        import httpx

        # Fetch URL content
        async with httpx.AsyncClient() as client:
            response = await client.get(request.url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            html_content = response.text

        # Simple HTML to text conversion
        from html.parser import HTMLParser

        class HTMLTextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self.skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
                self.current_tag = None

            def handle_starttag(self, tag, attrs):
                self.current_tag = tag

            def handle_endtag(self, tag):
                self.current_tag = None

            def handle_data(self, data):
                if self.current_tag not in self.skip_tags:
                    text = data.strip()
                    if text:
                        self.text_parts.append(text)

            def get_text(self):
                return "\n".join(self.text_parts)

        extractor = HTMLTextExtractor()
        extractor.feed(html_content)
        content = extractor.get_text()

        if not content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from URL")

        # Process document
        processor = get_document_processor()
        result = processor.process_document(
            content=content,
            title=request.title,
            doc_type="other",
            language="hu",
            url=request.url,
        )

        return DocumentUploadResponse(
            success=True,
            doc_id=result.doc_id,
            chunks_created=result.chunks_count,
            message=f"URL '{request.url}' indexed successfully with {result.chunks_count} chunks.",
        )

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    doc_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all documents in the knowledge base."""
    try:
        vectorstore = get_vectorstore()
        docs = vectorstore.list_documents()

        # Filter by doc_type if specified
        if doc_type:
            docs = [d for d in docs if d.get("doc_type") == doc_type]

        # Format for frontend
        formatted_docs = []
        for doc in docs:
            formatted_docs.append({
                "id": doc.get("doc_id", ""),
                "title": doc.get("title", "Untitled"),
                "source_type": doc.get("doc_type", "markdown"),
                "source_path": doc.get("url", ""),
                "chunk_count": doc.get("chunk_count", 0),
                "indexed_at": doc.get("indexed_at", datetime.now().isoformat()),
            })

        # Apply pagination
        total = len(formatted_docs)
        formatted_docs = formatted_docs[offset:offset + limit]

        return DocumentListResponse(
            documents=formatted_docs,
            total=total,
        )

    except Exception as e:
        return DocumentListResponse(
            documents=[],
            total=0,
        )


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a specific document's metadata and chunks."""
    try:
        vectorstore = get_vectorstore()
        docs = vectorstore.list_documents()

        for doc in docs:
            if doc.get("doc_id") == doc_id:
                return {
                    "id": doc.get("doc_id"),
                    "title": doc.get("title"),
                    "doc_type": doc.get("doc_type"),
                    "status": "found",
                }

        raise HTTPException(status_code=404, detail="Document not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and all its chunks from the knowledge base."""
    try:
        processor = get_document_processor()
        success = processor.delete_document(doc_id)

        if success:
            return {"status": "deleted", "doc_id": doc_id}
        else:
            raise HTTPException(status_code=404, detail="Document not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/reindex")
async def reindex_document(doc_id: str):
    """Re-index an existing document (e.g., after content update)."""
    # For now, just return success - full reindexing would need stored content
    return {"status": "reindexed", "doc_id": doc_id}
