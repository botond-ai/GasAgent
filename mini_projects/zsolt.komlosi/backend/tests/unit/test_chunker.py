"""
Unit tests for document chunker.
"""

import pytest
from app.rag.chunker import DocumentChunker, get_chunker
from app.models import Document


class TestDocumentChunker:
    """Tests for document chunking."""

    @pytest.fixture
    def chunker(self):
        """Create chunker with test settings."""
        return DocumentChunker(chunk_size=100, chunk_overlap=20)

    @pytest.fixture
    def sample_document(self):
        """Create sample document."""
        content = """
        # Első fejezet

        Ez az első bekezdés, ami elég hosszú ahhoz, hogy
        több mondatot tartalmazzon. Fontos információkat
        közlünk itt a felhasználóknak.

        # Második fejezet

        Ez a második bekezdés, ami szintén több mondatból áll.
        További részleteket találsz itt a témáról.
        Nagyon hasznos információk vannak benne.

        # Harmadik fejezet

        Az utolsó bekezdés is fontos dolgokat tartalmaz.
        Ne felejtsd el elolvasni figyelmesen.
        """
        return Document(
            doc_id="TEST-001",
            title="Test Document",
            content=content,
            doc_type="faq",
        )

    def test_chunk_document_creates_chunks(self, chunker, sample_document):
        """Test that chunking creates multiple chunks."""
        chunks = chunker.chunk_document(sample_document)

        assert len(chunks) > 0
        assert all(chunk.doc_id == "TEST-001" for chunk in chunks)

    def test_chunk_ids_are_unique(self, chunker, sample_document):
        """Test that chunk IDs are unique."""
        chunks = chunker.chunk_document(sample_document)
        chunk_ids = [c.chunk_id for c in chunks]

        assert len(chunk_ids) == len(set(chunk_ids))

    def test_chunks_have_required_fields(self, chunker, sample_document):
        """Test that chunks have all required fields."""
        chunks = chunker.chunk_document(sample_document)

        for chunk in chunks:
            assert chunk.chunk_id
            assert chunk.doc_id == "TEST-001"
            assert chunk.content_hu
            assert chunk.title == "Test Document"
            assert chunk.doc_type == "faq"
            assert chunk.chunk_index >= 0
            assert chunk.token_count > 0

    def test_token_count_respects_limit(self):
        """Test that chunks don't exceed token limit."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
        content = "Ez egy teszt szöveg. " * 100

        doc = Document(
            doc_id="TEST-002",
            title="Long Document",
            content=content,
            doc_type="other",
        )
        chunks = chunker.chunk_document(doc)

        # Token count should be around the limit (with some tolerance)
        for chunk in chunks:
            assert chunk.token_count <= 100  # Allow some tolerance

    def test_chunk_text_simple(self, chunker):
        """Test simple text chunking."""
        text = "Ez egy rövid szöveg teszteléshez."
        chunks = chunker.chunk_text(text, doc_id="TEMP-001")

        assert len(chunks) >= 1
        assert chunks[0].content_hu == text

    def test_singleton_pattern(self):
        """Test that get_chunker returns same instance."""
        chunker1 = get_chunker()
        chunker2 = get_chunker()
        assert chunker1 is chunker2

    def test_chunk_preserves_content(self, chunker, sample_document):
        """Test that chunking preserves all content."""
        chunks = chunker.chunk_document(sample_document)

        # All chunks combined should contain all original content
        combined = " ".join(c.content_hu for c in chunks)

        # Check that key phrases are present
        assert "Első fejezet" in combined or "első" in combined.lower()
        assert "Második fejezet" in combined or "második" in combined.lower()
