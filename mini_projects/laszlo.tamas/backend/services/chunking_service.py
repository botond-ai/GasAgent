"""Document chunking service with TOC-aware smart chunking."""

import logging
from typing import List, Dict, Tuple, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from database.document_chunk_repository import DocumentChunkRepository
from services.protocols import IDocumentChunkRepository, DocumentChunkDict

logger = logging.getLogger(__name__)

# Character approximation
CHAR_PER_TOKEN = 4  # rough approximation: 1 token ≈ 4 characters


class ChunkingService:
    """Service for splitting documents into chunks."""
    
    def __init__(self, repository: IDocumentChunkRepository):
        """
        Initialize ChunkingService with dependency injection.
        
        Args:
            repository: Document chunk repository implementation
        """
        from services.config_service import get_config_service
        
        # Load from system.ini
        config = get_config_service()
        self.chunk_size = config.get_chunk_size_tokens()
        self.chunk_overlap = config.get_chunk_overlap_tokens()
        
        self.repository = repository
        
        # Initialize RecursiveCharacterTextSplitter
        # Convert token size to character size (rough approximation)
        chunk_size_chars = self.chunk_size * CHAR_PER_TOKEN
        chunk_overlap_chars = self.chunk_overlap * CHAR_PER_TOKEN
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size_chars,
            chunk_overlap=chunk_overlap_chars,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        logger.info(
            f"ChunkingService initialized: "
            f"chunk_size={chunk_size_chars} chars (~{self.chunk_size} tokens), "
            f"overlap={chunk_overlap_chars} chars (~{self.chunk_overlap} tokens)"
        )
    
    def chunk_document(
        self,
        document_id: int,
        tenant_id: int,
        content: str,
        source_title: str
    ) -> List[int]:
        """
        Split document content into chunks and store in database.
        
        Args:
            document_id: Document identifier (FK to documents.id)
            tenant_id: Tenant identifier
            content: Full document text content
            source_title: Document title for metadata
        
        Returns:
            List of created chunk IDs
        
        Raises:
            ValueError: If content is empty
        """
        if not content or not content.strip():
            raise ValueError("Document content is empty")
        
        logger.info(f"Chunking document_id={document_id}, content_length={len(content)} chars")
        
        # Split text into chunks
        text_chunks = self.text_splitter.split_text(content)
        
        logger.info(f"Created {len(text_chunks)} chunks")
        
        # Calculate offsets and prepare chunk data
        chunks_data = []
        current_offset = 0
        
        for idx, chunk_text in enumerate(text_chunks):
            # Find chunk position in original text
            # Note: This is approximate due to overlap handling
            start_offset = content.find(chunk_text, current_offset)
            
            if start_offset == -1:
                # Fallback: use current offset
                start_offset = current_offset
            
            end_offset = start_offset + len(chunk_text)
            
            chunks_data.append({
                "chunk_index": idx,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "content": chunk_text,
                "source_title": source_title
            })
            
            # Move offset for next chunk
            current_offset = start_offset + len(chunk_text)
        
        # Insert chunks into database
        chunk_ids = self.repository.insert_chunks(
            tenant_id=tenant_id,
            document_id=document_id,
            chunks=chunks_data
        )
        
        logger.info(
            f"Document {document_id} chunked: {len(chunk_ids)} chunks, "
            f"avg_length={sum(len(c['content']) for c in chunks_data) / len(chunks_data):.0f} chars"
        )
        
        return chunk_ids
    
    def get_document_chunks(self, document_id: int) -> List[DocumentChunkDict]:
        """
        Retrieve all chunks for a document.
        
        Args:
            document_id: Document identifier
        
        Returns:
            List of chunk dictionaries
        """
        return self.repository.get_chunks_by_document(document_id)
    
    def chunk_document_with_structure(
        self,
        document_id: int,
        tenant_id: int,
        content: str,
        source_title: str,
        toc: List[Tuple[int, str, int]] = None,
        page_texts: Dict[int, str] = None
    ) -> List[int]:
        """
        Smart chunking with TOC awareness and page tracking.
        
        Strategy:
        1. If TOC exists: Chunk by chapter/section boundaries
        2. If chapter too large: Sub-chunk with RecursiveCharacterTextSplitter
        3. Enrich each chunk with metadata: chapter_name, page_start/end, section_level
        
        Args:
            document_id: Document ID
            tenant_id: Tenant ID
            content: Full document text
            source_title: Document title
            toc: List of (level, title, page_num) from TOC extraction
            page_texts: Dict mapping page numbers to text content
        
        Returns:
            List of created chunk IDs
        """
        if not content or not content.strip():
            raise ValueError("Document content is empty")
        
        # If no TOC, fallback to standard chunking
        if not toc or len(toc) == 0:
            logger.info("No TOC available, using standard character-based chunking")
            return self.chunk_document(document_id, tenant_id, content, source_title)
        
        logger.info(
            f"Smart chunking with TOC: {len(toc)} entries, "
            f"{len(page_texts or {})} pages"
        )
        
        chunks_data = []
        chunk_idx = 0
        
        # Process each TOC entry
        for i, (level, title, start_page) in enumerate(toc):
            # Determine end page (next chapter or document end)
            end_page = toc[i + 1][2] if i + 1 < len(toc) else max(page_texts.keys())
            
            # Extract section text
            section_text = self._extract_section_text(
                page_texts, start_page, end_page
            )
            
            if not section_text.strip():
                continue
            
            # Find offsets in full content
            start_offset = content.find(section_text[:100])  # First 100 chars
            if start_offset == -1:
                start_offset = 0  # Fallback
            end_offset = start_offset + len(section_text)
            
            # Check if section is too large
            max_chunk_size = self.chunk_size * CHAR_PER_TOKEN
            
            if len(section_text) > max_chunk_size:
                # Sub-chunk large section
                sub_chunks = self.text_splitter.split_text(section_text)
                
                for sub_idx, sub_text in enumerate(sub_chunks):
                    chunks_data.append({
                        "chunk_index": chunk_idx,
                        "start_offset": start_offset,
                        "end_offset": start_offset + len(sub_text),
                        "content": sub_text,
                        "source_title": source_title,
                        "chapter_name": title,
                        "page_start": start_page,
                        "page_end": end_page,
                        "section_level": level
                    })
                    chunk_idx += 1
                    start_offset += len(sub_text)
            else:
                # Keep chapter intact
                chunks_data.append({
                    "chunk_index": chunk_idx,
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "content": section_text,
                    "source_title": source_title,
                    "chapter_name": title,
                    "page_start": start_page,
                    "page_end": end_page,
                    "section_level": level
                })
                chunk_idx += 1
        
        # Insert enriched chunks
        chunk_ids = self.repository.insert_chunks(
            tenant_id=tenant_id,
            document_id=document_id,
            chunks=chunks_data
        )
        
        logger.info(
            f"Smart chunking complete: {len(chunk_ids)} chunks created, "
            f"avg_size={sum(len(c['content']) for c in chunks_data) / len(chunks_data):.0f} chars"
        )
        
        return chunk_ids
    
    def _extract_section_text(
        self, 
        page_texts: Dict[int, str], 
        start_page: int, 
        end_page: int
    ) -> str:
        """Extract text from page range."""
        text_parts = []
        
        for page_num in range(start_page, end_page + 1):
            if page_num in page_texts:
                text_parts.append(page_texts[page_num])
        
        return "\n".join(text_parts)
