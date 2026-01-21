"""
Document chunking with RecursiveCharacterTextSplitter.
600 tokens per chunk, 80 token overlap.
"""

from typing import List, Optional
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.models import Document, Chunk


class DocumentChunker:
    """
    Document chunker using RecursiveCharacterTextSplitter.
    Configured with 600 tokens per chunk, 80 token overlap.

    Creates chunks with Hungarian content (content_hu).
    English translation (content_en) is filled in later by DocumentProcessor.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        settings = get_settings()
        self.chunk_size = chunk_size or settings.rag_chunk_size
        self.chunk_overlap = chunk_overlap or settings.rag_chunk_overlap

        # Use tiktoken for accurate token counting
        self.encoding = tiktoken.encoding_for_model("gpt-4")

        # Create splitter with token-based length function
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=self._count_tokens,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        return len(self.encoding.encode(text))

    def chunk_document(
        self,
        document: Document,
        translated_content: Optional[str] = None,
    ) -> List[Chunk]:
        """
        Split a document into chunks.

        Args:
            document: Document to chunk
            translated_content: Optional English translation (deprecated, use DocumentProcessor for translation)

        Returns:
            List of Chunk objects with content_hu set, content_en empty (to be filled later)
        """
        content = document.content

        # Split the content
        text_chunks = self.splitter.split_text(content)

        chunks = []
        current_pos = 0

        for i, hu_chunk in enumerate(text_chunks):
            # Find position in original content
            start_pos = content.find(hu_chunk[:50], current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(hu_chunk)
            current_pos = end_pos - self.chunk_overlap * 4  # Approximate character overlap

            chunk = Chunk(
                chunk_id=f"{document.doc_id}-chunk-{i:03d}",
                doc_id=document.doc_id,
                content_hu=hu_chunk,
                content_en="",  # Will be filled by DocumentProcessor
                title=document.title,
                doc_type=document.doc_type,
                chunk_index=i,
                start_char=max(0, start_pos),
                end_char=end_pos,
                token_count=self._count_tokens(hu_chunk),
                url=document.url,
                keywords=[],  # Will be populated by DocumentProcessor
            )
            chunks.append(chunk)

        return chunks

    def chunk_text(
        self,
        text: str,
        doc_id: str = "temp",
        title: str = "Untitled",
        doc_type: str = "other",
    ) -> List[Chunk]:
        """
        Split plain text into chunks.

        Args:
            text: Text to chunk
            doc_id: Document ID to use
            title: Title for the chunks
            doc_type: Document type

        Returns:
            List of Chunk objects
        """
        doc = Document(
            doc_id=doc_id,
            title=title,
            content=text,
            doc_type=doc_type,
        )
        return self.chunk_document(doc)


# Singleton instance
_chunker = None


def get_chunker() -> DocumentChunker:
    """Get or create the chunker singleton."""
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker
