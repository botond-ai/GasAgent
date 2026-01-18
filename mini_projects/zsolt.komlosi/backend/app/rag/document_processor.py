"""
Document processing pipeline for RAG.
Handles: load -> chunk -> translate -> extract keywords -> embed -> store

Pipeline:
1. Load document (Hungarian)
2. Chunk the Hungarian content
3. Translate each chunk to English (ensures 1:1 mapping)
4. Extract English keywords using AI
5. Generate embeddings for English content
6. Store in vector DB and BM25 index
"""

from typing import List, Optional
import uuid
import logging
from datetime import datetime

from app.config import get_settings
from app.models import Document, Chunk, DocumentInfo
from .chunker import get_chunker
from .embeddings import get_embedding_service
from .vectorstore import get_vectorstore
from .bm25 import get_bm25_index

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Complete document processing pipeline.

    Key features:
    - Chunk-by-chunk Hungarian to English translation (ensures alignment)
    - AI-powered keyword extraction (in English)
    - Hybrid storage (vector DB + BM25)
    """

    def __init__(self):
        self.chunker = get_chunker()
        self.embedding_service = get_embedding_service()
        self.vectorstore = get_vectorstore()
        self.bm25_index = get_bm25_index()
        self._llm = None

    @property
    def llm(self):
        """Lazy-load LLM to avoid initialization issues."""
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            settings = get_settings()
            self._llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.3,
            )
        return self._llm

    def process_document(
        self,
        content: str,
        title: str,
        doc_type: str,
        language: str = "hu",
        doc_id: Optional[str] = None,
        url: Optional[str] = None,
    ) -> DocumentInfo:
        """
        Process a document through the full pipeline.

        Args:
            content: Document content (markdown or plain text)
            title: Document title
            doc_type: Type of document (aszf, faq, user_guide, policy, other)
            language: Document language (hu, en)
            doc_id: Optional document ID (generated if not provided)
            url: Optional URL to the document

        Returns:
            DocumentInfo with processing results
        """
        # Generate doc_id if not provided
        if doc_id is None:
            doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"

        logger.info(f"Processing document: {doc_id} - {title}")

        # Create Document model
        document = Document(
            doc_id=doc_id,
            title=title,
            content=content,
            doc_type=doc_type,
            language=language,
            url=url,
        )

        # Step 1: Chunk the Hungarian document first
        logger.info(f"Chunking document {doc_id}...")
        chunks = self.chunker.chunk_document(document)
        logger.info(f"Created {len(chunks)} chunks for {doc_id}")

        # Step 2: Translate each chunk to English and extract keywords
        if language == "hu":
            logger.info(f"Translating {len(chunks)} chunks from Hungarian to English...")
            for i, chunk in enumerate(chunks):
                # Translate chunk to English
                chunk.content_en = self._translate_chunk(chunk.content_hu)

                # Extract English keywords using AI
                chunk.keywords = self._extract_keywords_ai(chunk.content_en, chunk.title)

                if (i + 1) % 3 == 0 or (i + 1) == len(chunks):
                    logger.info(f"Processed {i + 1}/{len(chunks)} chunks (translation + keywords)")
        else:
            # Document is already in English
            logger.info(f"Document is in English, extracting keywords...")
            for i, chunk in enumerate(chunks):
                chunk.content_en = chunk.content_hu  # Same content
                chunk.keywords = self._extract_keywords_ai(chunk.content_en, chunk.title)

        # Step 3: Store in vector database
        logger.info(f"Storing {len(chunks)} chunks in vector database...")
        chunks_stored = self.vectorstore.add_chunks(chunks)

        # Step 4: Add to BM25 index
        self._add_to_bm25(chunks)
        logger.info(f"Document {doc_id} fully indexed with {chunks_stored} chunks")

        return DocumentInfo(
            doc_id=doc_id,
            title=title,
            doc_type=doc_type,
            language=language,
            chunks_count=chunks_stored,
            indexed_at=datetime.now().isoformat(),
            status="indexed",
        )

    def _translate_chunk(self, text: str) -> str:
        """
        Translate a single chunk from Hungarian to English.
        """
        try:
            response = self.llm.invoke(
                f"Translate the following Hungarian text to English. "
                f"Preserve all formatting, structure, and technical terms. "
                f"Only output the translation, nothing else.\n\n{text}"
            )
            return response.content
        except Exception as e:
            logger.error(f"Translation failed for chunk: {e}")
            # Return original text as fallback
            return text

    def _extract_keywords_ai(self, text: str, title: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords from text using AI.

        Uses LLM to identify the most important and searchable
        keywords/phrases from the content.
        """
        try:
            response = self.llm.invoke(
                f"Extract the {max_keywords} most important keywords or short phrases "
                f"from the following text. These keywords should be useful for search "
                f"and retrieval. Output only the keywords, one per line, in English.\n\n"
                f"Title: {title}\n\n"
                f"Content:\n{text[:2000]}"  # Limit content to avoid token limits
            )

            # Parse keywords from response
            keywords = []
            for line in response.content.strip().split("\n"):
                keyword = line.strip().strip("- ").strip("• ").strip("*").strip()
                if keyword and len(keyword) > 2:
                    # Remove numbering if present
                    if keyword[0].isdigit() and "." in keyword[:3]:
                        keyword = keyword.split(".", 1)[1].strip()
                    keywords.append(keyword.lower())

            return keywords[:max_keywords]

        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            # Fallback to simple extraction
            return self._extract_keywords_simple(text, max_keywords)

    def _extract_keywords_simple(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Simple keyword extraction based on word frequency.
        Used as fallback when AI extraction fails.
        """
        import re
        from collections import Counter

        # English stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "and", "but", "or", "nor", "so", "yet", "both", "either",
            "neither", "not", "only", "own", "same", "than", "too",
            "very", "just", "also", "now", "here", "there", "when",
            "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no",
            "this", "that", "these", "those", "what", "which", "who",
        }

        # Tokenize and clean
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
        words = [w for w in words if len(w) > 3 and w not in stop_words]

        # Get most common words
        word_counts = Counter(words)
        keywords = [word for word, _ in word_counts.most_common(max_keywords)]

        return keywords

    def _add_to_bm25(self, chunks: List[Chunk]) -> None:
        """Add chunks to BM25 index for hybrid search."""
        documents = [
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "content_hu": chunk.content_hu,
                "content_en": chunk.content_en,
                "title": chunk.title,
                "doc_type": chunk.doc_type,
                "url": chunk.url,
                "keywords": chunk.keywords,
            }
            for chunk in chunks
        ]
        self.bm25_index.add_documents(documents)

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from all indices.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if successful
        """
        logger.info(f"Deleting document {doc_id}")

        # Delete from vector store
        success = self.vectorstore.delete_by_doc_id(doc_id)

        # BM25 index would need to be rebuilt (simplified for now)
        # In production, implement proper deletion from BM25

        return success


# Singleton instance
_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """Get or create the document processor singleton."""
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor
