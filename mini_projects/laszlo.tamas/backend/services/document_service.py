"""Document processing service with TOC extraction."""

import logging
from typing import Literal, Dict, List, Tuple, Optional
from pypdf import PdfReader
from io import BytesIO
import chardet

try:
    import fitz  # PyMuPDF (import as fitz)
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("PyMuPDF not available, TOC extraction disabled")

from database.document_repository import DocumentRepository
from services.protocols import IDocumentRepository
from services.exceptions import DocumentServiceError

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document upload and processing."""
    
    def __init__(self, repository: IDocumentRepository):
        """
        Initialize DocumentService with dependency injection.
        
        Args:
            repository: Document repository implementation
        """
        self.repository = repository
    
    async def upload_document(
        self,
        filename: str,
        content: bytes,
        file_type: str,
        tenant_id: int,
        user_id: int,
        visibility: Literal["private", "tenant"]
    ) -> int:
        """
        Process uploaded document and store in database.
        
        Args:
            filename: Original filename
            content: File content as bytes
            file_type: File extension (.pdf, .txt, .md)
            tenant_id: Tenant identifier
            user_id: User identifier
            visibility: Document visibility level
        
        Returns:
            document_id: ID of created document
        
        Raises:
            DocumentServiceError: If file content cannot be extracted
        """
        logger.info(f"Processing document: {filename} ({file_type})")
        
        # Extract text content based on file type
        text_content = self._extract_content(content, file_type, filename)
        
        if not text_content or not text_content.strip():
            raise DocumentServiceError(
                "Document is empty or could not be read",
                context={
                    "filename": filename,
                    "file_type": file_type,
                    "content_size": len(content),
                    "operation": "upload_document"
                }
            )
        
        # Store in database (sync call)
        document_id = self.repository.insert_document(
            tenant_id=tenant_id,
            user_id=user_id,
            visibility=visibility,
            source="upload",
            title=filename,
            content=text_content
        )
        
        logger.info(f"Document stored: id={document_id}, length={len(text_content)} chars")
        
        return document_id
    
    def _extract_content(self, content: bytes, file_type: str, filename: str = "unknown") -> str:
        """
        Extract text content from file bytes.
        
        Args:
            content: File content as bytes
            file_type: File extension
            filename: Original filename for error context
        
        Returns:
            Extracted text content
        
        Raises:
            DocumentServiceError: If extraction fails
        """
        try:
            if file_type == ".pdf":
                return self._extract_pdf(content)
            elif file_type in [".txt", ".md"]:
                return self._extract_text(content)
            else:
                raise DocumentServiceError(
                    f"Unsupported file type: {file_type}",
                    context={
                        "filename": filename,
                        "file_type": file_type,
                        "supported_types": [".pdf", ".txt", ".md"],
                        "operation": "extract_content"
                    }
                )
        except DocumentServiceError:
            # Re-raise DocumentServiceError as-is
            raise
        except Exception as e:
            logger.error(f"Content extraction error ({file_type}): {e}", exc_info=True)
            raise DocumentServiceError(
                f"Failed to extract content from {file_type} file",
                context={
                    "filename": filename,
                    "file_type": file_type,
                    "content_size": len(content),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "operation": "extract_content"
                }
            ) from e
    
    def _extract_pdf(self, content: bytes) -> str:
        """Extract text from PDF bytes."""
        pdf_file = BytesIO(content)
        reader = PdfReader(pdf_file)
        
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        return "\n".join(text_parts)
    
    def _extract_text(self, content: bytes) -> str:
        """Extract text from TXT/MD bytes using automatic encoding detection."""
        # Use chardet to detect the actual encoding
        detection = chardet.detect(content)
        detected_encoding = detection.get('encoding')
        confidence = detection.get('confidence', 0)
        
        logger.info(f"Detected encoding: {detected_encoding} (confidence: {confidence:.2f})")
        
        # Try detected encoding first if confidence is high enough
        if detected_encoding and confidence > 0.7:
            try:
                decoded = content.decode(detected_encoding)
                logger.info(f"Successfully decoded with {detected_encoding}")
                return decoded
            except (UnicodeDecodeError, LookupError) as e:
                logger.warning(f"Failed to decode with detected encoding {detected_encoding}: {e}")
        
        # Fallback: try common encodings
        encodings = ["utf-8", "cp1250", "cp1252", "latin-1", "iso-8859-2"]
        
        for encoding in encodings:
            try:
                decoded = content.decode(encoding)
                logger.info(f"Successfully decoded with fallback encoding: {encoding}")
                return decoded
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Last resort: utf-8 with error replacement
        logger.warning("All encodings failed, using UTF-8 with error replacement")
        return content.decode("utf-8", errors="replace")
    
    def extract_with_structure(
        self, 
        content: bytes, 
        file_type: str, 
        filename: str = "unknown"
    ) -> Dict[str, any]:
        """
        Extract text content WITH structural metadata (TOC, pages).
        
        Returns enriched document data for smart chunking:
        - full_text: Complete text content
        - toc: List of (level, title, page_num) if available
        - page_texts: Dict mapping page numbers to text content
        - has_structure: Boolean indicating if TOC was found
        
        Args:
            content: File content as bytes
            file_type: File extension
            filename: Original filename for context
        
        Returns:
            Dict with keys: full_text, toc, page_texts, has_structure
        """
        if file_type == ".pdf" and PYMUPDF_AVAILABLE:
            return self._extract_pdf_with_structure(content)
        else:
            # Fallback: plain text extraction
            text = self._extract_content(content, file_type, filename)
            return {
                "full_text": text,
                "toc": [],
                "page_texts": {1: text},  # Single "page"
                "has_structure": False
            }
    
    def _extract_pdf_with_structure(self, content: bytes) -> Dict[str, any]:
        """
        Extract PDF with full structural metadata using PyMuPDF.
        
        Returns:
            {
                "full_text": str,
                "toc": [(level, title, page_num), ...],
                "page_texts": {page_num: text, ...},
                "has_structure": bool
            }
        """
        doc = fitz.open(stream=content, filetype="pdf")
        
        # 1. Extract TOC (if exists)
        toc = doc.get_toc()  # [(level, title, page_num), ...]
        
        # 2. Extract text per page
        page_texts = {}
        full_text_parts = []
        
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            page_texts[page_num] = text
            full_text_parts.append(text)
        
        full_text = "\n".join(full_text_parts)
        
        # 3. If no TOC, try font-based detection
        if not toc:
            logger.info(f"No embedded TOC found, attempting font-based detection")
            toc = self._detect_headings_by_font(doc)
        
        has_structure = len(toc) > 0
        
        logger.info(
            f"PDF structure extracted: "
            f"{len(doc)} pages, {len(toc)} TOC entries, "
            f"{len(full_text)} chars, structure={'Yes' if has_structure else 'No'}"
        )
        
        return {
            "full_text": full_text,
            "toc": toc,
            "page_texts": page_texts,
            "has_structure": has_structure
        }
    
    def _detect_headings_by_font(self, doc) -> List[Tuple[int, str, int]]:
        """
        Detect chapter headings by font size (heuristic fallback).
        
        Returns:
            List of (level, title, page_num) tuples
        """
        headings = []
        
        for page in doc:
            blocks = page.get_text("dict").get("blocks", [])
            
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_size = span.get("size", 0)
                        text = span.get("text", "").strip()
                        
                        # Heuristic: Large font = heading
                        if font_size > 14 and len(text) > 3:
                            level = 1 if font_size > 18 else 2
                            headings.append((level, text, page.number + 1))
                            break  # One heading per line
        
        logger.info(f"Font-based heading detection found {len(headings)} headings")
        return headings
