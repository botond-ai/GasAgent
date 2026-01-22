import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

from core.document_processor import DocumentProcessor
from infrastructure.vector_store import VectorStore, Domain
from core.markdown_chunker import MarkdownRAGChunker
from presentation.display_writer_interface import DisplayWriterInterface


@pytest.fixture
def mock_vector_store():
    store = MagicMock(spec=VectorStore)
    store.find_by_title = MagicMock(return_value=None)
    store.delete_by_title = MagicMock(return_value=0)
    store.add_document_chunk = AsyncMock(return_value="chunk_id")
    return store


@pytest.fixture
def mock_chunker():
    chunker = MagicMock(spec=MarkdownRAGChunker)
    chunker.load_markdown = MagicMock(return_value="# Test Document\n\nContent here")
    chunker.chunk_document = MagicMock(return_value=[
        {"text": "Chunk 1 content", "header": "Test", "h1": "Test", "id": "1"},
        {"text": "Chunk 2 content", "header": "Test", "h1": "Test", "id": "2"}
    ])
    return chunker


@pytest.fixture
def mock_display_writer():
    writer = MagicMock(spec=DisplayWriterInterface)
    writer.write = MagicMock()
    return writer


@pytest.fixture
def document_processor(mock_vector_store, mock_chunker, mock_display_writer):
    return DocumentProcessor(
        vector_store=mock_vector_store,
        chunker=mock_chunker,
        display_writer=mock_display_writer
    )


@pytest.fixture
def temp_markdown_file(tmp_path):
    """Create a temporary markdown file for testing."""
    file_path = tmp_path / "test_doc.md"
    file_path.write_text("# Test Document\n\nThis is test content.", encoding="utf-8")
    return file_path


class TestDocumentProcessorInit:
    def test_init_sets_vector_store(self, document_processor, mock_vector_store):
        assert document_processor.vector_store == mock_vector_store

    def test_init_sets_chunker(self, document_processor, mock_chunker):
        assert document_processor.chunker == mock_chunker

    def test_init_sets_display_writer(self, document_processor, mock_display_writer):
        assert document_processor.display_writer == mock_display_writer


class TestProcessDocument:
    @pytest.mark.asyncio
    async def test_processes_new_document(
        self, document_processor, mock_vector_store, mock_display_writer, temp_markdown_file
    ):
        mock_vector_store.find_by_title.return_value = None

        result = await document_processor.process_document(temp_markdown_file, Domain.HR)

        assert result is True
        mock_display_writer.write.assert_any_call(f"  [NEW] {temp_markdown_file.name}\n")

    @pytest.mark.asyncio
    async def test_skips_unchanged_document(
        self, document_processor, mock_vector_store, mock_display_writer, temp_markdown_file
    ):
        # Calculate the actual hash of the file
        file_hash = hashlib.sha256(temp_markdown_file.read_bytes()).hexdigest()

        mock_vector_store.find_by_title.return_value = {
            "ids": ["chunk1"],
            "metadata": {"hash": file_hash}
        }

        result = await document_processor.process_document(temp_markdown_file, Domain.HR)

        assert result is False
        mock_display_writer.write.assert_any_call(f"  [SKIP] {temp_markdown_file.name} - unchanged\n")

    @pytest.mark.asyncio
    async def test_updates_changed_document(
        self, document_processor, mock_vector_store, mock_display_writer, temp_markdown_file
    ):
        mock_vector_store.find_by_title.return_value = {
            "ids": ["old_chunk1", "old_chunk2"],
            "metadata": {"hash": "old_hash_different_from_current"}
        }
        mock_vector_store.delete_by_title.return_value = 2

        result = await document_processor.process_document(temp_markdown_file, Domain.HR)

        assert result is True
        mock_vector_store.delete_by_title.assert_called_once_with(temp_markdown_file.name, Domain.HR)
        mock_display_writer.write.assert_any_call(f"  [UPDATE] {temp_markdown_file.name} - deleted 2 old chunks\n")

    @pytest.mark.asyncio
    async def test_calls_vector_store_find_by_title(
        self, document_processor, mock_vector_store, temp_markdown_file
    ):
        await document_processor.process_document(temp_markdown_file, Domain.IT)

        mock_vector_store.find_by_title.assert_called_once_with(temp_markdown_file.name, Domain.IT)

    @pytest.mark.asyncio
    async def test_adds_chunks_to_vector_store(
        self, document_processor, mock_vector_store, mock_chunker, temp_markdown_file
    ):
        mock_chunker.chunk_document.return_value = [
            {"text": "Chunk 1", "header": "H1", "h1": "H1", "id": "1"},
            {"text": "Chunk 2", "header": "H1", "h1": "H1", "id": "2"},
        ]

        await document_processor.process_document(temp_markdown_file, Domain.HR)

        assert mock_vector_store.add_document_chunk.call_count == 2


class TestProcessDocuments:
    @pytest.mark.asyncio
    async def test_processes_multiple_documents(
        self, document_processor, mock_display_writer, tmp_path
    ):
        file1 = tmp_path / "doc1.md"
        file2 = tmp_path / "doc2.md"
        file1.write_text("# Doc 1\nContent", encoding="utf-8")
        file2.write_text("# Doc 2\nContent", encoding="utf-8")

        count = await document_processor.process_documents(
            [str(file1), str(file2)],
            Domain.HR
        )

        assert count == 2

    @pytest.mark.asyncio
    async def test_returns_count_of_processed_documents(
        self, document_processor, mock_vector_store, tmp_path
    ):
        file1 = tmp_path / "doc1.md"
        file2 = tmp_path / "doc2.md"
        file3 = tmp_path / "doc3.md"
        file1.write_text("# Doc 1\nContent", encoding="utf-8")
        file2.write_text("# Doc 2\nContent", encoding="utf-8")
        file3.write_text("# Doc 3\nContent", encoding="utf-8")

        # Make doc2 unchanged (skip it)
        file2_hash = hashlib.sha256(file2.read_bytes()).hexdigest()

        def find_by_title_side_effect(title, domain):
            if title == "doc2.md":
                return {"ids": ["chunk1"], "metadata": {"hash": file2_hash}}
            return None

        mock_vector_store.find_by_title.side_effect = find_by_title_side_effect

        count = await document_processor.process_documents(
            [str(file1), str(file2), str(file3)],
            Domain.HR
        )

        assert count == 2  # doc1 and doc3 processed, doc2 skipped

    @pytest.mark.asyncio
    async def test_writes_processing_header(
        self, document_processor, mock_display_writer, tmp_path
    ):
        file1 = tmp_path / "doc1.md"
        file1.write_text("# Doc 1\nContent", encoding="utf-8")

        await document_processor.process_documents([str(file1)], Domain.HR)

        mock_display_writer.write.assert_any_call("Processing documents for ingestion...\n")


class TestIngestDocument:
    @pytest.mark.asyncio
    async def test_loads_markdown_from_chunker(
        self, document_processor, mock_chunker, temp_markdown_file
    ):
        await document_processor._ingest_document(
            filepath=temp_markdown_file,
            title="test.md",
            source="/path/test.md",
            file_hash="abc123",
            domain=Domain.HR
        )

        mock_chunker.load_markdown.assert_called_once_with(str(temp_markdown_file))

    @pytest.mark.asyncio
    async def test_chunks_document(
        self, document_processor, mock_chunker, temp_markdown_file
    ):
        await document_processor._ingest_document(
            filepath=temp_markdown_file,
            title="test.md",
            source="/path/test.md",
            file_hash="abc123",
            domain=Domain.HR
        )

        mock_chunker.chunk_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_adds_each_chunk_to_vector_store(
        self, document_processor, mock_vector_store, mock_chunker, temp_markdown_file
    ):
        mock_chunker.chunk_document.return_value = [
            {"text": "Chunk A", "header": "H", "h1": "H", "id": "1"},
            {"text": "Chunk B", "header": "H", "h1": "H", "id": "2"},
            {"text": "Chunk C", "header": "H", "h1": "H", "id": "3"},
        ]

        await document_processor._ingest_document(
            filepath=temp_markdown_file,
            title="test.md",
            source="/path/test.md",
            file_hash="abc123",
            domain=Domain.FINANCE
        )

        assert mock_vector_store.add_document_chunk.call_count == 3

    @pytest.mark.asyncio
    async def test_passes_correct_metadata_to_vector_store(
        self, document_processor, mock_vector_store, mock_chunker, temp_markdown_file
    ):
        mock_chunker.chunk_document.return_value = [
            {"text": "Test chunk", "header": "H", "h1": "H", "id": "1"}
        ]

        with patch("uuid.uuid4", return_value="test-uuid"):
            await document_processor._ingest_document(
                filepath=temp_markdown_file,
                title="my_doc.md",
                source="/docs/my_doc.md",
                file_hash="hash123",
                domain=Domain.LEGAL
            )

        call_kwargs = mock_vector_store.add_document_chunk.call_args.kwargs
        assert call_kwargs["text"] == "Test chunk"
        assert call_kwargs["domain"] == Domain.LEGAL
        assert call_kwargs["metadata"]["title"] == "my_doc.md"
        assert call_kwargs["metadata"]["source"] == "/docs/my_doc.md"
        assert call_kwargs["metadata"]["hash"] == "hash123"

    @pytest.mark.asyncio
    async def test_writes_chunk_count(
        self, document_processor, mock_display_writer, mock_chunker, temp_markdown_file
    ):
        mock_chunker.chunk_document.return_value = [
            {"text": "Chunk 1", "header": "H", "h1": "H", "id": "1"},
            {"text": "Chunk 2", "header": "H", "h1": "H", "id": "2"},
        ]

        await document_processor._ingest_document(
            filepath=temp_markdown_file,
            title="test.md",
            source="/path/test.md",
            file_hash="abc123",
            domain=Domain.HR
        )

        mock_display_writer.write.assert_any_call("    Added 2 chunks\n")

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(
        self, document_processor, mock_display_writer, mock_chunker, temp_markdown_file
    ):
        mock_chunker.load_markdown.side_effect = Exception("File read error")

        # Should not raise
        await document_processor._ingest_document(
            filepath=temp_markdown_file,
            title="test.md",
            source="/path/test.md",
            file_hash="abc123",
            domain=Domain.HR
        )

        # Should write error message
        error_call = [
            call for call in mock_display_writer.write.call_args_list
            if "[ERROR]" in str(call)
        ]
        assert len(error_call) == 1


class TestComputeFileHash:
    def test_computes_sha256_hash(self, document_processor, tmp_path):
        file_path = tmp_path / "test.txt"
        content = "Hello, World!"
        file_path.write_text(content, encoding="utf-8")

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        actual_hash = document_processor._compute_file_hash(file_path)

        assert actual_hash == expected_hash

    def test_same_content_produces_same_hash(self, document_processor, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "Same content"
        file1.write_text(content, encoding="utf-8")
        file2.write_text(content, encoding="utf-8")

        hash1 = document_processor._compute_file_hash(file1)
        hash2 = document_processor._compute_file_hash(file2)

        assert hash1 == hash2

    def test_different_content_produces_different_hash(self, document_processor, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content A", encoding="utf-8")
        file2.write_text("Content B", encoding="utf-8")

        hash1 = document_processor._compute_file_hash(file1)
        hash2 = document_processor._compute_file_hash(file2)

        assert hash1 != hash2

    def test_handles_large_files(self, document_processor, tmp_path):
        file_path = tmp_path / "large.txt"
        # Create a file larger than the 4096 byte buffer
        content = "X" * 10000
        file_path.write_text(content, encoding="utf-8")

        # Should not raise
        hash_result = document_processor._compute_file_hash(file_path)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 produces 64 hex characters

    def test_handles_binary_content(self, document_processor, tmp_path):
        file_path = tmp_path / "binary.bin"
        binary_content = bytes([0x00, 0xFF, 0x10, 0x20])
        file_path.write_bytes(binary_content)

        expected_hash = hashlib.sha256(binary_content).hexdigest()
        actual_hash = document_processor._compute_file_hash(file_path)

        assert actual_hash == expected_hash
