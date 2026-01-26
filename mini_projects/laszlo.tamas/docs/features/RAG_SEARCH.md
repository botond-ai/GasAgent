# RAG Search - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A RAG (Retrieval-Augmented Generation) rendszer tenant-specifikus dokumentumokban keres szemantikus hasonlóság alapján. A keresés figyelembe veszi a document visibility-t (tenant/private) és intelligent citation-öket biztosít.

## Használat

### Alapvető RAG keresés
```python
from services.rag_service import RAGService

rag = RAGService()

# Szemantikus dokumentum keresés
results = await rag.search_documents(
    query="mi a szabályzat a távmunkáról?",
    tenant_id=1,
    top_k=5,
    min_similarity=0.7
)

for result in results:
    print(f"Document: {result.source_title}")
    print(f"Relevance: {result.similarity_score:.2f}")
    print(f"Content: {result.content[:200]}...")
    print("---")
```

### User-specific private search
```python
# Keresés private dokumentumokban
private_results = await rag.search_private_documents(
    query="my personal notes about project X",
    tenant_id=1,
    user_id=1,
    top_k=3
)
```

### Enhanced search with filters
```python
# Szűrt keresés dokumentum típus és dátum alapján
filtered_results = await rag.advanced_search(
    query="budget planning for Q2",
    tenant_id=1,
    filters={
        "chapter_contains": "budget",
        "created_after": "2024-01-01",
        "source_types": ["pdf", "docx"]
    }
)
```

## Technikai implementáció

### RAG Service Architecture

```python
class RAGService:
    def __init__(self):
        self.vector_store = QdrantVectorStore()
        self.embedder = OpenAIEmbedder()
        self.db = DocumentRepository()
        self.reranker = DocumentReranker()
    
    async def search_documents(
        self,
        query: str,
        tenant_id: int,
        user_id: Optional[int] = None,
        top_k: int = 5,
        min_similarity: float = 0.7,
        include_private: bool = False
    ) -> List[DocumentSearchResult]:
        """
        Comprehensive document search with tenant isolation.
        
        Args:
            query: Search query
            tenant_id: Tenant for isolation
            user_id: User for private document access
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            include_private: Whether to include private documents
            
        Returns:
            List of DocumentSearchResult objects
        """
        
        # Generate query embedding
        query_embedding = await self.embedder.generate_embedding(query)
        
        # Build search filters for tenant isolation
        search_filter = self._build_tenant_search_filter(
            tenant_id=tenant_id,
            user_id=user_id if include_private else None,
            include_private=include_private
        )
        
        # Vector search in Qdrant
        vector_results = await self.vector_store.search(
            collection_name="document_chunks",
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=top_k * 2,  # Get more for reranking
            score_threshold=min_similarity
        )
        
        # Convert to structured results
        search_results = []
        for hit in vector_results:
            result = DocumentSearchResult(
                chunk_id=hit.payload["chunk_id"],
                document_id=hit.payload["document_id"],
                content=hit.payload["content"],
                source_title=hit.payload["source_title"],
                chapter_name=hit.payload.get("chapter_name"),
                page_start=hit.payload.get("page_start"),
                page_end=hit.payload.get("page_end"),
                similarity_score=hit.score,
                tenant_id=tenant_id
            )
            search_results.append(result)
        
        # Rerank results for better relevance
        reranked_results = await self.reranker.rerank_results(
            query=query,
            results=search_results[:top_k * 2]
        )
        
        return reranked_results[:top_k]
    
    def _build_tenant_search_filter(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        include_private: bool = False
    ) -> Filter:
        """Build Qdrant filter for tenant and visibility isolation."""
        
        filter_conditions = [
            # Always filter by tenant
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=tenant_id)
            )
        ]
        
        if include_private and user_id:
            # Include both tenant-wide and user's private documents
            visibility_filter = Filter(
                should=[
                    # Tenant-wide documents
                    FieldCondition(
                        key="visibility",
                        match=MatchValue(value="tenant")
                    ),
                    # User's private documents
                    Filter(
                        must=[
                            FieldCondition(
                                key="visibility",
                                match=MatchValue(value="private")
                            ),
                            FieldCondition(
                                key="user_id",
                                match=MatchValue(value=user_id)
                            )
                        ]
                    )
                ]
            )
            filter_conditions.append(visibility_filter)
        else:
            # Only tenant-wide documents
            filter_conditions.append(
                FieldCondition(
                    key="visibility",
                    match=MatchValue(value="tenant")
                )
            )
        
        return Filter(must=filter_conditions)

class DocumentReranker:
    """Rerank search results using multiple relevance signals."""
    
    async def rerank_results(
        self,
        query: str,
        results: List[DocumentSearchResult]
    ) -> List[DocumentSearchResult]:
        """Rerank results using multiple signals."""
        
        # Calculate additional relevance scores
        for result in results:
            # Keyword overlap score
            keyword_score = self._calculate_keyword_overlap(query, result.content)
            
            # Position bonus (earlier pages/chapters may be more important)
            position_score = self._calculate_position_bonus(result)
            
            # Length penalty (very short or very long chunks)
            length_score = self._calculate_length_score(result.content)
            
            # Combine scores
            result.combined_score = (
                result.similarity_score * 0.6 +  # Vector similarity
                keyword_score * 0.2 +           # Keyword match
                position_score * 0.1 +          # Document position
                length_score * 0.1              # Content length
            )
        
        # Sort by combined score
        return sorted(results, key=lambda r: r.combined_score, reverse=True)
    
    def _calculate_keyword_overlap(self, query: str, content: str) -> float:
        """Calculate keyword overlap between query and content."""
        
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words.intersection(content_words))
        return overlap / len(query_words)
```

### Advanced RAG Features

#### Hybrid Search (Vector + Keyword)
```python
class HybridSearchService:
    async def hybrid_search(
        self,
        query: str,
        tenant_id: int,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[DocumentSearchResult]:
        """Combine vector and keyword search for better recall."""
        
        # Vector search
        vector_results = await self.rag_service.search_documents(
            query=query,
            tenant_id=tenant_id,
            top_k=20
        )
        
        # Keyword search using PostgreSQL full-text search
        keyword_results = await self.keyword_search(query, tenant_id, top_k=20)
        
        # Combine and reweight results
        combined_results = self._combine_search_results(
            vector_results=vector_results,
            keyword_results=keyword_results,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight
        )
        
        return combined_results[:10]  # Return top 10
    
    async def keyword_search(
        self, 
        query: str, 
        tenant_id: int, 
        top_k: int = 20
    ) -> List[DocumentSearchResult]:
        """PostgreSQL full-text search for keyword matching."""
        
        # Use PostgreSQL's full-text search capabilities
        search_query = """
        SELECT 
            dc.id as chunk_id,
            dc.document_id,
            dc.content,
            dc.source_title,
            dc.chapter_name,
            dc.page_start,
            dc.page_end,
            ts_rank(to_tsvector('hungarian', dc.content), plainto_tsquery('hungarian', %(query)s)) as rank
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE d.tenant_id = %(tenant_id)s
        AND d.visibility = 'tenant'
        AND to_tsvector('hungarian', dc.content) @@ plainto_tsquery('hungarian', %(query)s)
        ORDER BY rank DESC
        LIMIT %(limit)s
        """
        
        results = await self.db.execute(search_query, {
            "query": query,
            "tenant_id": tenant_id,
            "limit": top_k
        })
        
        return [
            DocumentSearchResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                content=r["content"],
                source_title=r["source_title"],
                chapter_name=r["chapter_name"],
                page_start=r["page_start"],
                page_end=r["page_end"],
                similarity_score=float(r["rank"]),
                search_method="keyword"
            )
            for r in results
        ]
```

#### Query Enhancement
```python
class QueryEnhancer:
    """Enhance user queries for better RAG retrieval."""
    
    async def enhance_query(
        self,
        original_query: str,
        user_context: UserContext,
        conversation_history: List[ChatMessage] = None
    ) -> str:
        """Enhance query with context and expansion."""
        
        enhanced_parts = [original_query]
        
        # Add context from conversation
        if conversation_history:
            context = self._extract_context_keywords(conversation_history)
            if context:
                enhanced_parts.append(f"Context: {' '.join(context)}")
        
        # Query expansion with synonyms
        synonyms = await self._get_query_synonyms(original_query)
        if synonyms:
            enhanced_parts.append(f"Related: {' '.join(synonyms)}")
        
        return " ".join(enhanced_parts)
    
    async def _get_query_synonyms(self, query: str) -> List[str]:
        """Get synonyms for query terms to improve recall."""
        
        # Simple synonym dictionary (could be enhanced with ML)
        synonym_dict = {
            "szabályzat": ["policy", "rule", "guideline"],
            "távmunka": ["remote work", "home office", "telework"],
            "költségvetés": ["budget", "financial plan"],
            "projekt": ["project", "initiative"]
        }
        
        query_words = query.lower().split()
        synonyms = []
        
        for word in query_words:
            if word in synonym_dict:
                synonyms.extend(synonym_dict[word])
        
        return synonyms[:3]  # Limit to avoid query bloat
```

### RAG Citation and Attribution

```python
class CitationGenerator:
    """Generate proper citations for RAG search results."""
    
    def generate_citations(
        self,
        search_results: List[DocumentSearchResult],
        language: str = "hu"
    ) -> List[Citation]:
        """Generate structured citations from search results."""
        
        citations = []
        for i, result in enumerate(search_results, 1):
            citation = Citation(
                number=i,
                source_title=result.source_title,
                chapter_name=result.chapter_name,
                page_start=result.page_start,
                page_end=result.page_end,
                similarity_score=result.similarity_score,
                content_preview=result.content[:150] + "..." if len(result.content) > 150 else result.content
            )
            citations.append(citation)
        
        return citations
    
    def format_citations_for_response(
        self,
        citations: List[Citation],
        language: str = "hu"
    ) -> str:
        """Format citations for inclusion in response."""
        
        if not citations:
            return ""
        
        header = "**Források:**" if language == "hu" else "**Sources:**"
        citation_lines = [header]
        
        for citation in citations:
            line_parts = [f"[{citation.number}] {citation.source_title}"]
            
            if citation.chapter_name:
                line_parts.append(f" - {citation.chapter_name}")
            
            if citation.page_start:
                if language == "hu":
                    if citation.page_end and citation.page_end != citation.page_start:
                        line_parts.append(f" (oldal {citation.page_start}-{citation.page_end})")
                    else:
                        line_parts.append(f" (oldal {citation.page_start})")
                else:
                    if citation.page_end and citation.page_end != citation.page_start:
                        line_parts.append(f" (pages {citation.page_start}-{citation.page_end})")
                    else:
                        line_parts.append(f" (page {citation.page_start})")
            
            citation_lines.append("".join(line_parts))
        
        return "\n".join(citation_lines)
```

## Funkció-specifikus konfiguráció

### RAG Search Configuration
```ini
# Search parameters
DEFAULT_TOP_K=5
MIN_SIMILARITY_THRESHOLD=0.7
MAX_SIMILARITY_THRESHOLD=1.0
ENABLE_RERANKING=true

# Vector search
VECTOR_SEARCH_TIMEOUT_SEC=10
QDRANT_SEARCH_LIMIT=50
ENABLE_HYBRID_SEARCH=true

# Query enhancement
ENABLE_QUERY_ENHANCEMENT=true
MAX_QUERY_SYNONYMS=3
ENABLE_CONTEXT_EXPANSION=true

# Citation settings
MAX_CITATIONS_PER_RESPONSE=5
CITATION_PREVIEW_LENGTH=150
ENABLE_SOURCE_ATTRIBUTION=true
```

### Performance Optimization
```python
# Result caching for repeated queries
class RAGCache:
    async def get_cached_results(
        self, 
        query_hash: str, 
        tenant_id: int
    ) -> Optional[List[DocumentSearchResult]]:
        cache_key = f"rag:{tenant_id}:{query_hash}"
        return await redis_client.get(cache_key)
    
    async def cache_results(
        self,
        query_hash: str,
        tenant_id: int,
        results: List[DocumentSearchResult],
        ttl: int = 300
    ):
        cache_key = f"rag:{tenant_id}:{query_hash}"
        await redis_client.setex(cache_key, ttl, pickle.dumps(results))

# Batch embedding for efficiency
async def batch_search_multiple_queries(
    queries: List[str],
    tenant_id: int
) -> Dict[str, List[DocumentSearchResult]]:
    # Generate all embeddings in one batch
    embeddings = await embedder.generate_batch_embeddings(queries)
    
    # Execute searches in parallel
    search_tasks = [
        rag_service.search_documents_with_embedding(embedding, tenant_id)
        for embedding in embeddings
    ]
    
    results = await asyncio.gather(*search_tasks)
    return dict(zip(queries, results))
```