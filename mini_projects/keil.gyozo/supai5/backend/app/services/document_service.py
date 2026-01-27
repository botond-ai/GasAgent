"""
Document processing service for knowledge base ingestion.
"""
import uuid
import io
from typing import Optional, BinaryIO
from datetime import datetime

# PDF processing
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# DOCX processing
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.core.logging import get_logger
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)


class DocumentService:
    """Service for processing and indexing documents."""

    def __init__(self, qdrant_service: QdrantService):
        """
        Initialize document service.

        Args:
            qdrant_service: Qdrant service instance
        """
        self.qdrant = qdrant_service
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=settings.openai_api_key
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        logger.info("Initialized DocumentService")

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        title: str,
        category: str,
        description: Optional[str] = None
    ) -> dict:
        """
        Process and index a document.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            title: Document title
            category: Document category
            description: Optional description

        Returns:
            Document metadata with processing stats
        """
        # Extract text based on file type
        file_extension = filename.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            text = self._extract_text_from_pdf(file_content)
        elif file_extension == 'docx':
            text = self._extract_text_from_docx(file_content)
        elif file_extension in ['txt', 'md']:
            text = file_content.decode('utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        if not text.strip():
            raise ValueError("No text could be extracted from the document")

        # Generate document ID
        doc_id = str(uuid.uuid4())

        # Split into chunks
        chunks = self.text_splitter.split_text(text)
        logger.info(f"Split document {doc_id} into {len(chunks)} chunks")

        # Generate embeddings
        embeddings = await self.embeddings.aembed_documents(chunks)
        logger.info(f"Generated {len(embeddings)} embeddings for document {doc_id}")

        # Prepare metadata
        metadata = {
            "title": title,
            "category": category,
            "description": description or "",
            "filename": filename,
            "file_type": file_extension,
            "created_at": datetime.utcnow().isoformat(),
            "chunk_count": len(chunks)
        }

        # Upsert to Qdrant
        await self.qdrant.upsert_documents(
            doc_id=doc_id,
            chunks=chunks,
            embeddings=embeddings,
            metadata=metadata
        )

        logger.info(f"Successfully indexed document: {doc_id} ({title})")

        return {
            "id": doc_id,
            "title": title,
            "category": category,
            "description": description or "",
            "filename": filename,
            "file_type": file_extension,
            "chunk_count": len(chunks),
            "created_at": metadata["created_at"]
        }

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """
        Extract text from PDF file.

        Args:
            file_content: PDF file bytes

        Returns:
            Extracted text
        """
        if PyPDF2 is None:
            raise ImportError("PyPDF2 is not installed. Install with: pip install PyPDF2")

        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_parts = []
        for page in pdf_reader.pages:
            text_parts.append(page.extract_text())
        
        return "\n\n".join(text_parts)

    def _extract_text_from_docx(self, file_content: bytes) -> str:
        """
        Extract text from DOCX file.

        Args:
            file_content: DOCX file bytes

        Returns:
            Extracted text
        """
        if DocxDocument is None:
            raise ImportError("python-docx is not installed. Install with: pip install python-docx")

        docx_file = io.BytesIO(file_content)
        doc = DocxDocument(docx_file)
        
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        return "\n\n".join(text_parts)

    async def list_documents(
        self,
        category: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """
        List all indexed documents.

        Args:
            category: Optional category filter
            limit: Maximum number of documents

        Returns:
            List of document metadata
        """
        # Query Qdrant for unique documents
        # We'll use a dummy vector and fetch by metadata
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        query_filter = None
        if category:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category)
                    )
                ]
            )

        # Get all points and extract unique documents
        # Note: This is a simplified approach. For production, 
        # you'd want a separate metadata store or better querying
        try:
            # Scroll through all points
            points, _ = await self.qdrant.client.scroll(
                collection_name=self.qdrant.collection_name,
                scroll_filter=query_filter,
                limit=limit * 10,  # Fetch more to account for chunks
                with_payload=True,
                with_vectors=False
            )

            # Group by doc_id and get first chunk metadata
            docs_dict = {}
            for point in points:
                doc_id = point.payload.get("doc_id")
                if doc_id and doc_id not in docs_dict:
                    docs_dict[doc_id] = {
                        "id": doc_id,
                        "title": point.payload.get("title", "Untitled"),
                        "category": point.payload.get("category", "Unknown"),
                        "description": point.payload.get("description", ""),
                        "filename": point.payload.get("filename", ""),
                        "file_type": point.payload.get("file_type", ""),
                        "created_at": point.payload.get("created_at", ""),
                        "chunk_count": point.payload.get("chunk_count", 0)
                    }

            # Sort by created_at descending
            documents = list(docs_dict.values())
            documents.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return documents[:limit]

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    async def get_document_with_chunks(self, doc_id: str) -> dict | None:
        """
        Get document metadata and all text chunks.

        Args:
            doc_id: Document ID

        Returns:
            Document with chunks or None if not found
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Find all points with this doc_id
            points, _ = await self.qdrant.client.scroll(
                collection_name=self.qdrant.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                return None

            # Extract metadata from first chunk
            first_point = points[0]
            document = {
                "id": doc_id,
                "title": first_point.payload.get("title", "Untitled"),
                "category": first_point.payload.get("category", "Unknown"),
                "description": first_point.payload.get("description", ""),
                "filename": first_point.payload.get("filename", ""),
                "file_type": first_point.payload.get("file_type", ""),
                "created_at": first_point.payload.get("created_at", ""),
                "chunk_count": first_point.payload.get("chunk_count", len(points)),
                "chunks": []
            }

            # Extract chunks and sort by index
            chunks = []
            for point in points:
                chunks.append({
                    "chunk_index": point.payload.get("chunk_index", 0),
                    "text": point.payload.get("text", "")
                })

            # Sort by chunk_index
            chunks.sort(key=lambda x: x["chunk_index"])
            document["chunks"] = chunks

            return document

        except Exception as e:
            logger.error(f"Error fetching document {doc_id}: {e}")
            return None

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks of a document.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if successful
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Find all points with this doc_id
            points, _ = await self.qdrant.client.scroll(
                collection_name=self.qdrant.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=False,
                with_vectors=False
            )

            # Delete all points
            point_ids = [point.id for point in points]
            if point_ids:
                await self.qdrant.client.delete(
                    collection_name=self.qdrant.collection_name,
                    points_selector=point_ids
                )
                logger.info(f"Deleted {len(point_ids)} chunks for document {doc_id}")
                return True
            else:
                logger.warning(f"No chunks found for document {doc_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False

    async def get_document_stats(self) -> dict:
        """
        Get statistics about the knowledge base.

        Returns:
            Statistics dictionary
        """
        try:
            collection_info = await self.qdrant.get_collection_info()
            documents = await self.list_documents(limit=1000)

            # Count by category
            category_counts = {}
            for doc in documents:
                category = doc.get("category", "Unknown")
                category_counts[category] = category_counts.get(category, 0) + 1

            return {
                "total_documents": len(documents),
                "total_chunks": collection_info.get("points_count", 0),
                "categories": category_counts,
                "collection_status": collection_info.get("status", "unknown")
            }

        except Exception as e:
            logger.error(f"Error getting document stats: {e}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "categories": {},
                "collection_status": "error"
            }
