# Vector Embeddings - Knowledge Router

## Mit csinál (felhasználói nézőpont)

Az embedding rendszer minden text content-et 1536-dimenziós vektorokká alakít OpenAI text-embedding-3-large modellel. Ezeket Qdrant vector database-ben tárolja tenant-specific isolationnel a szemantikus kereséshez.

## Használat

### Embedding generation
```python
from services.embedding_service import EmbeddingService

embedder = EmbeddingService()

# Egyszerű embedding
embedding = await embedder.generate_embedding("Mi a távmunka szabályzat?")
print(f"Embedding dimensions: {len(embedding)}")

# Batch embedding (hatékonyabb)
texts = ["query 1", "query 2", "query 3"]
embeddings = await embedder.generate_batch_embeddings(texts)
```

### Similarity search
```python
# Hasonló embeddings keresése
similar_chunks = await embedder.find_similar_embeddings(
    query_embedding=embedding,
    tenant_id=1,
    collection="document_chunks",
    top_k=5
)
```

## Technikai implementáció

### Embedding Service
```python
class EmbeddingService:
    def __init__(self):
        self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = "text-embedding-3-large"
        self.dimensions = 1536
        self.batch_size = 100
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate single embedding with error handling."""
        try:
            response = await self.openai_client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            log_error("Embedding generation failed", error=str(e))
            raise EmbeddingError(f"Failed to generate embedding: {str(e)}")
    
    async def generate_batch_embeddings(
        self, 
        texts: List[str]
    ) -> List[List[float]]:
        """Generate multiple embeddings efficiently."""
        embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            response = await self.openai_client.embeddings.create(
                model=self.model,
                input=batch,
                encoding_format="float"
            )
            
            batch_embeddings = [data.embedding for data in response.data]
            embeddings.extend(batch_embeddings)
        
        return embeddings

class QdrantEmbeddingStore:
    def __init__(self):
        self.client = QdrantClient(url=config.QDRANT_URL)
        self.collections = {
            "document_chunks": {"size": 1536, "distance": "Cosine"},
            "long_term_memories": {"size": 1536, "distance": "Cosine"}
        }
    
    async def store_embeddings(
        self,
        embeddings: List[EmbeddingPoint],
        collection_name: str
    ):
        """Store embeddings with tenant isolation."""
        points = []
        
        for embedding in embeddings:
            point = PointStruct(
                id=embedding.point_id,
                vector=embedding.vector,
                payload={
                    "tenant_id": embedding.tenant_id,  # Critical for isolation
                    **embedding.metadata
                }
            )
            points.append(point)
        
        operation = await self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        return operation.status == UpdateStatus.COMPLETED
```

### Performance Optimizations
```python
# Embedding caching
class EmbeddingCache:
    async def get_cached_embedding(self, text_hash: str) -> Optional[List[float]]:
        return await redis_client.get(f"embedding:{text_hash}")
    
    async def cache_embedding(self, text_hash: str, embedding: List[float]):
        await redis_client.setex(f"embedding:{text_hash}", 3600, pickle.dumps(embedding))

# Async batch processing
async def process_document_embeddings(document_chunks: List[DocumentChunk]):
    tasks = []
    for chunk in document_chunks:
        task = generate_and_store_embedding(chunk)
        tasks.append(task)
    
    await asyncio.gather(*tasks, return_exceptions=True)
```

## Funkció-specifikus konfiguráció

```ini
# OpenAI settings
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=1536
EMBEDDING_BATCH_SIZE=100
EMBEDDING_TIMEOUT_SEC=30

# Qdrant settings
QDRANT_URL=http://localhost:6333
VECTOR_DISTANCE_METRIC=Cosine
ENABLE_EMBEDDING_CACHE=true
CACHE_TTL_SEC=3600
```