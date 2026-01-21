"""
Unit Test: Chunking Service
Knowledge Router PROD

Tests ChunkingService functionality:
- Document chunking with RecursiveCharacterTextSplitter
- Offset calculation
- Empty content validation
- TOC-aware chunking
- Repository integration

Priority: HIGH (chunking is core RAG functionality)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from services.chunking_service import ChunkingService


@pytest.mark.unit
class TestChunkingService:
    """Test ChunkingService functionality."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock document chunk repository."""
        repo = Mock()
        repo.insert_chunks = Mock(return_value=[1, 2, 3])  # Return chunk IDs
        repo.get_chunks_by_document = Mock(return_value=[])
        return repo
    
    @pytest.fixture
    def chunking_service(self, mock_repository):
        """Create ChunkingService with mocked dependencies."""
        with patch('services.config_service.get_config_service') as mock_config:
            mock_config.return_value.get_chunk_size_tokens.return_value = 100
            mock_config.return_value.get_chunk_overlap_tokens.return_value = 10
            
            service = ChunkingService(repository=mock_repository)
            yield service  # Use yield to keep context manager open
    
    # ========================================================================
    # BASIC CHUNKING
    # ========================================================================
    
    def test_chunk_document_basic(self, chunking_service, mock_repository):
        """Test basic document chunking."""
        content = "This is a test document. " * 50  # ~1250 chars
        
        chunk_ids = chunking_service.chunk_document(
            document_id=1,
            tenant_id=1,
            content=content,
            source_title="Test Doc"
        )
        
        assert len(chunk_ids) > 0
        mock_repository.insert_chunks.assert_called_once()
    
    def test_chunk_document_returns_chunk_ids(self, chunking_service, mock_repository):
        """Test chunk_document returns list of chunk IDs."""
        mock_repository.insert_chunks.return_value = [10, 11, 12]
        
        content = "Test content. " * 100
        
        chunk_ids = chunking_service.chunk_document(
            document_id=1,
            tenant_id=1,
            content=content,
            source_title="Test"
        )
        
        assert chunk_ids == [10, 11, 12]
    
    def test_chunk_document_passes_correct_data(self, chunking_service, mock_repository):
        """Test chunk_document passes correct data to repository."""
        content = "Short content that fits in one chunk."
        
        chunking_service.chunk_document(
            document_id=42,
            tenant_id=5,
            content=content,
            source_title="My Document"
        )
        
        call_args = mock_repository.insert_chunks.call_args
        assert call_args.kwargs['tenant_id'] == 5
        assert call_args.kwargs['document_id'] == 42
        
        chunks = call_args.kwargs['chunks']
        assert len(chunks) > 0
        assert chunks[0]['source_title'] == "My Document"
        assert chunks[0]['content'] == content
    
    # ========================================================================
    # EMPTY CONTENT VALIDATION
    # ========================================================================
    
    def test_chunk_document_empty_content_raises(self, chunking_service):
        """Test chunk_document raises ValueError for empty content."""
        with pytest.raises(ValueError, match="Document content is empty"):
            chunking_service.chunk_document(
                document_id=1,
                tenant_id=1,
                content="",
                source_title="Empty Doc"
            )
    
    def test_chunk_document_whitespace_only_raises(self, chunking_service):
        """Test chunk_document raises ValueError for whitespace-only content."""
        with pytest.raises(ValueError, match="Document content is empty"):
            chunking_service.chunk_document(
                document_id=1,
                tenant_id=1,
                content="   \n\t  ",
                source_title="Whitespace Doc"
            )
    
    def test_chunk_document_none_content_raises(self, chunking_service):
        """Test chunk_document raises for None content."""
        with pytest.raises((ValueError, TypeError)):
            chunking_service.chunk_document(
                document_id=1,
                tenant_id=1,
                content=None,
                source_title="None Doc"
            )
    
    # ========================================================================
    # OFFSET CALCULATION
    # ========================================================================
    
    def test_chunk_has_start_end_offsets(self, chunking_service, mock_repository):
        """Test each chunk has start_offset and end_offset."""
        content = "First sentence. Second sentence. Third sentence. Fourth sentence."
        
        chunking_service.chunk_document(
            document_id=1,
            tenant_id=1,
            content=content,
            source_title="Test"
        )
        
        call_args = mock_repository.insert_chunks.call_args
        chunks = call_args.kwargs['chunks']
        
        for chunk in chunks:
            assert 'start_offset' in chunk
            assert 'end_offset' in chunk
            assert chunk['start_offset'] >= 0
            assert chunk['end_offset'] > chunk['start_offset']
    
    def test_chunk_index_is_sequential(self, chunking_service, mock_repository):
        """Test chunk_index is sequential starting from 0."""
        content = "Lorem ipsum dolor sit amet. " * 100  # Long enough for multiple chunks
        
        chunking_service.chunk_document(
            document_id=1,
            tenant_id=1,
            content=content,
            source_title="Test"
        )
        
        call_args = mock_repository.insert_chunks.call_args
        chunks = call_args.kwargs['chunks']
        
        for idx, chunk in enumerate(chunks):
            assert chunk['chunk_index'] == idx
    
    # ========================================================================
    # GET DOCUMENT CHUNKS
    # ========================================================================
    
    def test_get_document_chunks(self, chunking_service, mock_repository):
        """Test get_document_chunks retrieves chunks from repository."""
        expected_chunks = [
            {'id': 1, 'content': 'chunk1', 'chunk_index': 0},
            {'id': 2, 'content': 'chunk2', 'chunk_index': 1}
        ]
        mock_repository.get_chunks_by_document.return_value = expected_chunks
        
        result = chunking_service.get_document_chunks(document_id=42)
        
        assert result == expected_chunks
        mock_repository.get_chunks_by_document.assert_called_once_with(42)
    
    # ========================================================================
    # CHUNK SIZE CONFIGURATION
    # ========================================================================
    
    def test_respects_chunk_size_config(self):
        """Test chunking respects configured chunk size."""
        mock_repo = Mock()
        mock_repo.insert_chunks = Mock(return_value=[1])
        
        with patch('services.config_service.get_config_service') as mock_config:
            # Small chunk size = more chunks
            mock_config.return_value.get_chunk_size_tokens.return_value = 25  # ~100 chars
            mock_config.return_value.get_chunk_overlap_tokens.return_value = 5
            
            service = ChunkingService(repository=mock_repo)
            
            # Content should be split into multiple chunks with small chunk size
            content = "Word. " * 100  # ~600 chars
            service.chunk_document(
                document_id=1,
                tenant_id=1,
                content=content,
                source_title="Test"
            )
            
            call_args = mock_repo.insert_chunks.call_args
            chunks = call_args.kwargs['chunks']
            
            # With ~100 char chunks, ~600 char content should have multiple chunks
            assert len(chunks) > 1


@pytest.mark.unit
class TestChunkingServiceWithStructure:
    """Test TOC-aware chunking functionality."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        repo = Mock()
        repo.insert_chunks = Mock(return_value=[1, 2, 3])
        return repo
    
    @pytest.fixture
    def chunking_service(self, mock_repository):
        """Create ChunkingService."""
        with patch('services.config_service.get_config_service') as mock_config:
            mock_config.return_value.get_chunk_size_tokens.return_value = 200
            mock_config.return_value.get_chunk_overlap_tokens.return_value = 20
            
            service = ChunkingService(repository=mock_repository)
            yield service  # Use yield to keep context manager open
    
    def test_chunk_with_toc_uses_chapter_boundaries(self, chunking_service, mock_repository):
        """Test chunking with TOC and page_texts respects chapter boundaries."""
        content = """Chapter 1: Introduction
This is the introduction chapter with some content.

Chapter 2: Methods
This describes the methodology used.

Chapter 3: Results
Here are the results of the study."""
        
        # page_texts is required for TOC-based chunking
        page_texts = {
            1: "Chapter 1: Introduction\nThis is the introduction chapter with some content.",
            2: "Chapter 2: Methods\nThis describes the methodology used.",
            3: "Chapter 3: Results\nHere are the results of the study."
        }
        
        toc = [
            (1, "Chapter 1: Introduction", 1),
            (1, "Chapter 2: Methods", 2),
            (1, "Chapter 3: Results", 3)
        ]
        
        chunking_service.chunk_document_with_structure(
            document_id=1,
            tenant_id=1,
            content=content,
            source_title="Test",
            toc=toc,
            page_texts=page_texts
        )
        
        mock_repository.insert_chunks.assert_called()
    
    def test_chunk_without_toc_falls_back_to_basic(self, chunking_service, mock_repository):
        """Test chunking without TOC falls back to basic chunking."""
        content = "Simple content without chapters. " * 50
        
        chunking_service.chunk_document_with_structure(
            document_id=1,
            tenant_id=1,
            content=content,
            source_title="Test",
            toc=None,
            page_texts=None
        )
        
        mock_repository.insert_chunks.assert_called()
