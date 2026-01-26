"""
Unit Test: Hybrid Search Service
Knowledge Router PROD

Tests HybridSearchService functionality:
- Score normalization
- Weighted ranking
- Result merging and deduplication
- Vector-only and keyword-only fallback
- Document title enrichment

Priority: HIGH (hybrid search is core RAG functionality)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from services.hybrid_search_service import HybridSearchService


@pytest.mark.unit
class TestHybridSearchServiceNormalization:
    """Test score normalization logic."""
    
    @pytest.fixture
    def hybrid_service(self):
        """Create HybridSearchService with mocked dependencies."""
        mock_qdrant = Mock()
        mock_chunk_repo = Mock()
        mock_doc_repo = Mock()
        
        with patch('services.hybrid_search_service.get_config_value') as mock_config:
            mock_config.side_effect = lambda section, key, default: default
            
            service = HybridSearchService(
                qdrant_service=mock_qdrant,
                chunk_repo=mock_chunk_repo,
                document_repo=mock_doc_repo
            )
            return service
    
    def test_normalize_scores_basic(self, hybrid_service):
        """Test basic score normalization to [0, 1] range."""
        results = [
            {"chunk_id": 1, "score": 0.5},
            {"chunk_id": 2, "score": 1.0},
            {"chunk_id": 3, "score": 0.0}
        ]
        
        normalized = hybrid_service._normalize_and_weight(results, weight=1.0, source="test")
        
        # With weight=1.0, normalized scores should be in [0, 1]
        for result in normalized:
            assert 0.0 <= result["score"] <= 1.0
        
        # Highest original score should have highest normalized score
        scores = {r["chunk_id"]: r["score"] for r in normalized}
        assert scores[2] > scores[1] > scores[3]
    
    def test_normalize_with_weight(self, hybrid_service):
        """Test score normalization applies weight correctly."""
        results = [
            {"chunk_id": 1, "score": 1.0},  # Will normalize to 1.0, then weight
        ]
        
        # With weight=0.7
        normalized = hybrid_service._normalize_and_weight(results, weight=0.7, source="vector")
        
        # Single result normalizes to 1.0, then multiplied by 0.7
        assert normalized[0]["score"] == 0.7
    
    def test_normalize_empty_results(self, hybrid_service):
        """Test normalization handles empty results."""
        normalized = hybrid_service._normalize_and_weight([], weight=1.0, source="test")
        
        assert normalized == []
    
    def test_normalize_all_equal_scores(self, hybrid_service):
        """Test normalization when all scores are equal."""
        results = [
            {"chunk_id": 1, "score": 0.5},
            {"chunk_id": 2, "score": 0.5},
            {"chunk_id": 3, "score": 0.5}
        ]
        
        normalized = hybrid_service._normalize_and_weight(results, weight=0.7, source="test")
        
        # All equal scores should normalize to 1.0 (max), then weight
        for result in normalized:
            assert result["score"] == 0.7
    
    def test_normalize_preserves_original_score(self, hybrid_service):
        """Test normalization preserves original score for debugging."""
        results = [{"chunk_id": 1, "score": 0.85}]
        
        normalized = hybrid_service._normalize_and_weight(results, weight=1.0, source="test")
        
        assert normalized[0]["original_score"] == 0.85
    
    def test_normalize_adds_source_field(self, hybrid_service):
        """Test normalization adds source field."""
        results = [{"chunk_id": 1, "score": 0.5}]
        
        normalized = hybrid_service._normalize_and_weight(results, weight=1.0, source="vector")
        
        assert normalized[0]["source"] == "vector"


@pytest.mark.unit
class TestHybridSearchServiceMerging:
    """Test result merging and deduplication."""
    
    @pytest.fixture
    def hybrid_service(self):
        """Create HybridSearchService with mocked dependencies."""
        mock_qdrant = Mock()
        mock_chunk_repo = Mock()
        mock_doc_repo = Mock()
        
        with patch('services.hybrid_search_service.get_config_value') as mock_config:
            mock_config.side_effect = lambda section, key, default: default
            
            return HybridSearchService(
                qdrant_service=mock_qdrant,
                chunk_repo=mock_chunk_repo,
                document_repo=mock_doc_repo
            )
    
    def test_merge_no_overlap(self, hybrid_service):
        """Test merging results with no overlap."""
        vector_results = [
            {"chunk_id": 1, "score": 0.7, "source": "vector"},
            {"chunk_id": 2, "score": 0.5, "source": "vector"}
        ]
        keyword_results = [
            {"chunk_id": 3, "score": 0.3, "source": "keyword"},
            {"chunk_id": 4, "score": 0.2, "source": "keyword"}
        ]
        
        merged = hybrid_service._merge_results(vector_results, keyword_results)
        
        assert len(merged) == 4
        chunk_ids = {r["chunk_id"] for r in merged}
        assert chunk_ids == {1, 2, 3, 4}
    
    def test_merge_with_overlap_combines_scores(self, hybrid_service):
        """Test merging combines scores for overlapping chunks."""
        vector_results = [
            {"chunk_id": 1, "score": 0.7, "source": "vector"},
            {"chunk_id": 2, "score": 0.5, "source": "vector"}
        ]
        keyword_results = [
            {"chunk_id": 1, "score": 0.3, "source": "keyword"},  # Overlap!
            {"chunk_id": 3, "score": 0.2, "source": "keyword"}
        ]
        
        merged = hybrid_service._merge_results(vector_results, keyword_results)
        
        # Should have 3 unique chunks
        assert len(merged) == 3
        
        # Overlapping chunk should have combined score
        chunk_1 = next(r for r in merged if r["chunk_id"] == 1)
        assert chunk_1["score"] == 1.0  # 0.7 + 0.3
        assert chunk_1["source"] == "hybrid"
    
    def test_merge_empty_vector_results(self, hybrid_service):
        """Test merging with empty vector results."""
        keyword_results = [
            {"chunk_id": 1, "score": 0.5, "source": "keyword"}
        ]
        
        merged = hybrid_service._merge_results([], keyword_results)
        
        assert len(merged) == 1
        assert merged[0]["source"] == "keyword"
    
    def test_merge_empty_keyword_results(self, hybrid_service):
        """Test merging with empty keyword results."""
        vector_results = [
            {"chunk_id": 1, "score": 0.5, "source": "vector"}
        ]
        
        merged = hybrid_service._merge_results(vector_results, [])
        
        assert len(merged) == 1
        assert merged[0]["source"] == "vector"
    
    def test_merge_both_empty(self, hybrid_service):
        """Test merging with both empty results."""
        merged = hybrid_service._merge_results([], [])
        
        assert merged == []


@pytest.mark.unit
class TestHybridSearchServiceSearch:
    """Test full search functionality."""
    
    @pytest.fixture
    def mock_qdrant(self):
        """Create mock Qdrant service."""
        qdrant = Mock()
        qdrant.search_document_chunks.return_value = [
            {"chunk_id": 1, "document_id": 10, "score": 0.9, "content": "Vector result 1"},
            {"chunk_id": 2, "document_id": 10, "score": 0.8, "content": "Vector result 2"}
        ]
        return qdrant
    
    @pytest.fixture
    def mock_chunk_repo(self):
        """Create mock chunk repository."""
        repo = Mock()
        repo.search_fulltext.return_value = [
            {"chunk_id": 1, "document_id": 10, "score": 0.7, "content": "Keyword result 1"},
            {"chunk_id": 3, "document_id": 11, "score": 0.6, "content": "Keyword result 3"}
        ]
        repo.get_by_ids.return_value = []
        return repo
    
    @pytest.fixture
    def mock_doc_repo(self):
        """Create mock document repository."""
        repo = Mock()
        repo.get_document_by_id.return_value = {"id": 10, "title": "Test Document"}
        return repo
    
    @pytest.fixture
    def hybrid_service(self, mock_qdrant, mock_chunk_repo, mock_doc_repo):
        """Create HybridSearchService with mocks."""
        with patch('services.hybrid_search_service.get_config_value') as mock_config:
            mock_config.side_effect = lambda section, key, default: default
            
            return HybridSearchService(
                qdrant_service=mock_qdrant,
                chunk_repo=mock_chunk_repo,
                document_repo=mock_doc_repo
            )
    
    def test_search_calls_both_backends(self, hybrid_service, mock_qdrant, mock_chunk_repo):
        """Test search calls both vector and keyword search."""
        hybrid_service.search(
            query="test query",
            query_embedding=[0.1] * 3072,
            tenant_id=1,
            user_id=1,
            limit=10
        )
        
        mock_qdrant.search_document_chunks.assert_called_once()
        mock_chunk_repo.search_fulltext.assert_called_once()
    
    def test_search_returns_sorted_results(self, hybrid_service):
        """Test search returns results sorted by score descending."""
        results = hybrid_service.search(
            query="test",
            query_embedding=[0.1] * 3072,
            tenant_id=1,
            user_id=1,
            limit=10
        )
        
        # Results should be sorted by score descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_search_respects_limit(self, hybrid_service):
        """Test search respects limit parameter."""
        results = hybrid_service.search(
            query="test",
            query_embedding=[0.1] * 3072,
            tenant_id=1,
            user_id=1,
            limit=2
        )
        
        assert len(results) <= 2
    
    def test_search_vector_failure_fallback(self, hybrid_service, mock_qdrant, mock_chunk_repo):
        """Test search continues with keyword only when vector fails."""
        mock_qdrant.search_document_chunks.side_effect = Exception("Qdrant down")
        
        results = hybrid_service.search(
            query="test",
            query_embedding=[0.1] * 3072,
            tenant_id=1,
            user_id=1,
            limit=10
        )
        
        # Should still return keyword results
        assert len(results) > 0
        mock_chunk_repo.search_fulltext.assert_called_once()
    
    def test_search_keyword_failure_fallback(self, hybrid_service, mock_qdrant, mock_chunk_repo):
        """Test search continues with vector only when keyword fails."""
        mock_chunk_repo.search_fulltext.side_effect = Exception("DB connection error")
        
        results = hybrid_service.search(
            query="test",
            query_embedding=[0.1] * 3072,
            tenant_id=1,
            user_id=1,
            limit=10
        )
        
        # Should still return vector results
        assert len(results) > 0
        mock_qdrant.search_document_chunks.assert_called_once()


@pytest.mark.unit
class TestHybridSearchServiceConfig:
    """Test configuration handling."""
    
    def test_uses_config_weights(self):
        """Test service uses weights from config."""
        with patch('services.hybrid_search_service.get_config_value') as mock_config:
            # Custom weights
            def config_side_effect(section, key, default):
                if key == 'DEFAULT_VECTOR_WEIGHT':
                    return 0.8
                if key == 'DEFAULT_KEYWORD_WEIGHT':
                    return 0.2
                return default
            
            mock_config.side_effect = config_side_effect
            
            service = HybridSearchService(
                qdrant_service=Mock(),
                chunk_repo=Mock(),
                document_repo=Mock()
            )
            
            assert service.vector_weight == 0.8
            assert service.keyword_weight == 0.2
    
    def test_default_weights(self):
        """Test service uses default weights when config missing."""
        with patch('services.hybrid_search_service.get_config_value') as mock_config:
            mock_config.side_effect = lambda section, key, default: default
            
            service = HybridSearchService(
                qdrant_service=Mock(),
                chunk_repo=Mock(),
                document_repo=Mock()
            )
            
            assert service.vector_weight == 0.7
            assert service.keyword_weight == 0.3
