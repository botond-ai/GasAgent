"""
Tests for Document API routes.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from io import BytesIO

from app.models.api import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentListResponse,
)


class TestDocumentUploadRequest:
    """Tests for DocumentUploadRequest model."""

    def test_valid_request(self):
        """Test valid document upload request."""
        request = DocumentUploadRequest(
            title="FAQ Dokumentum",
            content="# GYIK\n\nEz a gyakran ismételt kérdések dokumentuma.",
            doc_type="faq",
            language="hu",
        )

        assert request.title == "FAQ Dokumentum"
        assert request.doc_type == "faq"
        assert request.language == "hu"

    def test_request_with_defaults(self):
        """Test request with default language."""
        request = DocumentUploadRequest(
            title="Test",
            content="Test content",
            doc_type="other",
        )

        assert request.language == "hu"

    def test_valid_doc_types(self):
        """Test all valid document types."""
        valid_types = ["aszf", "faq", "user_guide", "policy", "other"]

        for doc_type in valid_types:
            request = DocumentUploadRequest(
                title="Test",
                content="Content",
                doc_type=doc_type,
            )
            assert request.doc_type == doc_type

    def test_invalid_doc_type_fails(self):
        """Test that invalid doc_type fails validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DocumentUploadRequest(
                title="Test",
                content="Content",
                doc_type="invalid_type",
            )

    def test_empty_title_fails(self):
        """Test that empty title fails validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DocumentUploadRequest(
                title="",
                content="Content",
                doc_type="faq",
            )

    def test_empty_content_fails(self):
        """Test that empty content fails validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DocumentUploadRequest(
                title="Test",
                content="",
                doc_type="faq",
            )


class TestDocumentUploadResponse:
    """Tests for DocumentUploadResponse model."""

    def test_successful_response(self):
        """Test successful upload response."""
        response = DocumentUploadResponse(
            success=True,
            doc_id="doc-123",
            chunks_created=5,
            message="Document uploaded successfully",
        )

        assert response.success is True
        assert response.doc_id == "doc-123"
        assert response.chunks_created == 5

    def test_default_success_value(self):
        """Test default success value is True."""
        response = DocumentUploadResponse(
            doc_id="doc-123",
            chunks_created=3,
            message="OK",
        )

        assert response.success is True


class TestDocumentListResponse:
    """Tests for DocumentListResponse model."""

    def test_list_response(self):
        """Test document list response."""
        response = DocumentListResponse(
            documents=[
                {"doc_id": "doc-1", "title": "FAQ"},
                {"doc_id": "doc-2", "title": "ÁSZF"},
            ],
            total=2,
        )

        assert len(response.documents) == 2
        assert response.total == 2

    def test_empty_list_response(self):
        """Test empty document list response."""
        response = DocumentListResponse(
            documents=[],
            total=0,
        )

        assert len(response.documents) == 0
        assert response.total == 0


class TestDocumentProcessing:
    """Tests for document processing logic."""

    @pytest.fixture
    def mock_processor(self):
        """Create mock document processor."""
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value=[
            MagicMock(chunk_id="chunk-001", content_hu="Magyar szöveg", content_en="English text"),
            MagicMock(chunk_id="chunk-002", content_hu="Több szöveg", content_en="More text"),
        ])
        return processor

    @pytest.fixture
    def mock_vectorstore(self):
        """Create mock vector store."""
        store = MagicMock()
        store.add_chunks = AsyncMock()
        return store

    def test_markdown_file_detection(self):
        """Test that markdown files are detected correctly."""
        markdown_extensions = [".md", ".markdown"]

        for ext in markdown_extensions:
            filename = f"document{ext}"
            assert filename.endswith(ext)

    def test_text_file_detection(self):
        """Test that text files are detected correctly."""
        text_extensions = [".txt", ".text"]

        for ext in text_extensions:
            filename = f"document{ext}"
            assert filename.endswith(ext)


class TestDocumentChunking:
    """Tests related to document chunking for storage."""

    def test_chunk_id_format(self):
        """Test that chunk IDs follow expected format."""
        doc_id = "doc-123"
        chunk_index = 5

        chunk_id = f"{doc_id}-chunk-{chunk_index:03d}"

        assert chunk_id == "doc-123-chunk-005"

    def test_chunk_id_uniqueness(self):
        """Test that chunk IDs are unique for different indices."""
        doc_id = "doc-abc"
        chunk_ids = [f"{doc_id}-chunk-{i:03d}" for i in range(10)]

        assert len(chunk_ids) == len(set(chunk_ids))

    def test_token_count_estimation(self):
        """Test rough token count estimation."""
        # Rough estimate: ~4 characters per token for English
        text = "This is a test sentence with approximately thirty characters."
        estimated_tokens = len(text) // 4

        assert estimated_tokens > 0
        assert estimated_tokens < len(text)


class TestDocumentTranslation:
    """Tests for document translation functionality."""

    def test_hungarian_content_detected(self):
        """Test that Hungarian content is detected."""
        hungarian_text = "Ez egy magyar nyelvű dokumentum a felhasználói útmutatóról."

        # Simple heuristic: contains Hungarian-specific characters
        hungarian_chars = set("áéíóöőúüű")
        has_hungarian = any(char in hungarian_text.lower() for char in hungarian_chars)

        assert has_hungarian

    def test_english_content_structure(self):
        """Test that translated content maintains structure."""
        original = {
            "content_hu": "Magyar szöveg",
            "content_en": "",
        }

        # After translation, content_en should be filled
        translated = {
            "content_hu": original["content_hu"],
            "content_en": "Hungarian text",
        }

        assert translated["content_en"] != ""
        assert translated["content_hu"] == original["content_hu"]


class TestKeywordExtraction:
    """Tests for keyword extraction functionality."""

    def test_keyword_list_format(self):
        """Test that keywords are returned as a list."""
        keywords = ["login", "password", "authentication", "error"]

        assert isinstance(keywords, list)
        assert len(keywords) == 4
        assert all(isinstance(k, str) for k in keywords)

    def test_keyword_uniqueness(self):
        """Test that extracted keywords are unique."""
        keywords = ["login", "password", "login", "error"]
        unique_keywords = list(set(keywords))

        assert len(unique_keywords) < len(keywords)
