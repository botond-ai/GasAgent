"""
Integration Test: Qdrant Operations
Knowledge Router PROD

Tests Qdrant vector database operations:
- Connection
- Collection management
- Point upsert/delete
- Vector search
- Tenant isolation

Priority: MEDIUM (infrastructure)
"""

import pytest
import uuid
from qdrant_client.models import Distance, VectorParams
from services.config_service import get_config_service

# Load vector dimensions dynamically from config
VECTOR_DIMS = get_config_service().get_embedding_dimensions()


@pytest.mark.integration
class TestQdrantOperations:
    """Test Qdrant vector database operations."""
    
    def test_qdrant_connection(self, qdrant_client):
        """Test basic Qdrant connection."""
        collections = qdrant_client.get_collections()
        assert collections is not None
    
    def test_create_collection(self, qdrant_client):
        """Test collection creation."""
        collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
        
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_DIMS, distance=Distance.COSINE)
        )
        
        # Verify collection exists
        collections = qdrant_client.get_collections()
        collection_names = [col.name for col in collections.collections]
        assert collection_name in collection_names
        
        # Cleanup
        qdrant_client.delete_collection(collection_name)
    
    def test_upsert_point(self, qdrant_client, clean_qdrant_collection):
        """Test upserting a point to Qdrant."""
        import numpy as np
        
        point_id = str(uuid.uuid4())
        vector = np.random.rand(VECTOR_DIMS).tolist()
        
        qdrant_client.upsert(
            collection_name=clean_qdrant_collection,
            points=[{
                "id": point_id,
                "vector": vector,
                "payload": {
                    "chunk_id": 1,
                    "tenant_id": 1,
                    "test": True
                }
            }]
        )
        
        # Verify point exists
        point = qdrant_client.retrieve(
            collection_name=clean_qdrant_collection,
            ids=[point_id]
        )
        assert len(point) == 1
        assert point[0].id == point_id
    
    def test_search_points(self, qdrant_client, clean_qdrant_collection):
        """Test searching points in Qdrant."""
        import numpy as np
        
        # Insert test points
        vectors = [np.random.rand(VECTOR_DIMS).tolist() for _ in range(3)]
        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": vec,
                "payload": {"chunk_id": i, "tenant_id": 1}
            }
            for i, vec in enumerate(vectors)
        ]
        
        qdrant_client.upsert(
            collection_name=clean_qdrant_collection,
            points=points
        )
        
        # Search with first vector
        results = qdrant_client.search(
            collection_name=clean_qdrant_collection,
            query_vector=vectors[0],
            limit=3
        )
        
        assert len(results) > 0
        assert results[0].score > 0.99  # Should find exact match
    
    def test_tenant_isolation(self, qdrant_client, clean_qdrant_collection):
        """Test tenant isolation in Qdrant using filters."""
        import numpy as np
        
        # Insert points for different tenants
        tenant1_id = str(uuid.uuid4())
        tenant2_id = str(uuid.uuid4())
        
        points = [
            {
                "id": tenant1_id,
                "vector": np.random.rand(VECTOR_DIMS).tolist(),
                "payload": {"chunk_id": 1, "tenant_id": 1}
            },
            {
                "id": tenant2_id,
                "vector": np.random.rand(VECTOR_DIMS).tolist(),
                "payload": {"chunk_id": 2, "tenant_id": 2}
            }
        ]
        
        qdrant_client.upsert(
            collection_name=clean_qdrant_collection,
            points=points
        )
        
        # Search with tenant filter
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        results = qdrant_client.search(
            collection_name=clean_qdrant_collection,
            query_vector=np.random.rand(VECTOR_DIMS).tolist(),
            query_filter=Filter(
                must=[FieldCondition(key="tenant_id", match=MatchValue(value=1))]
            ),
            limit=10
        )
        
        # Should only return tenant 1 results
        assert all(point.payload["tenant_id"] == 1 for point in results)
    
    def test_delete_point(self, qdrant_client, clean_qdrant_collection):
        """Test deleting a point from Qdrant."""
        import numpy as np
        
        point_id = str(uuid.uuid4())
        
        # Insert point
        qdrant_client.upsert(
            collection_name=clean_qdrant_collection,
            points=[{
                "id": point_id,
                "vector": np.random.rand(VECTOR_DIMS).tolist(),
                "payload": {"chunk_id": 1, "tenant_id": 1}
            }]
        )
        
        # Delete point
        qdrant_client.delete(
            collection_name=clean_qdrant_collection,
            points_selector=[point_id]
        )
        
        # Verify deletion
        points = qdrant_client.retrieve(
            collection_name=clean_qdrant_collection,
            ids=[point_id]
        )
        assert len(points) == 0
