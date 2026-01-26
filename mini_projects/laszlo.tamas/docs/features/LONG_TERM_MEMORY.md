# Long-term Memory - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A hosszú távú memória rendszer user-specifikus információkat tárol és keres. Két típusú memóriát kezel: explicit faktákat ("jegyezd meg, hogy...") és session összefoglalókat (automatikus beszélgetés summák). Mindkét típus szemantikus kereshetőség.

## Használat

### Explicit memória létrehozás
```python
# "Jegyezd meg" funkció használata
from services.memory_service import LongTermMemoryService

memory_service = LongTermMemoryService()

# Explicit fact mentése
result = await memory_service.create_explicit_memory(
    user_id=1,
    tenant_id=1,
    content="Alice szereti a reggeli kávéját erősre főzni, és mindig oat milk-et tesz bele.",
    source_session_id="uuid-session-123"  # Optional
)

print(f"Memória ID: {result.memory_id}")
print(f"Embedding létrehozva: {result.embedded}")
```

### Memória keresés
```python
# Szemantikus memória keresés
memories = await memory_service.search_memories(
    query="mi Alice kedvenc itala?",
    user_id=1,
    memory_type="explicit_fact",  # vagy None az összes típushoz
    top_k=3
)

for memory in memories:
    print(f"Memória: {memory.content}")
    print(f"Relevancia: {memory.similarity_score:.2f}")
    print(f"Létrehozva: {memory.created_at}")
```

### Session summary automatikus létrehozás
```python
# Session lezárás és összefoglaló készítés
session_summary = await memory_service.create_session_summary(
    session_id="uuid-session-123",
    user_id=1,
    tenant_id=1
)

if session_summary:
    print(f"Session summary: {session_summary.content}")
```

### Batch memory operations
```python
# Több memória kezelése egyszerre
memory_batch = [
    "Alice kedvence a mediterrán konyha",
    "Bob projektvezető a marketing csapatban", 
    "Sarah home office-ban dolgozik keddenként és csütörtökönként"
]

results = await memory_service.create_multiple_memories(
    user_id=1,
    tenant_id=1,
    contents=memory_batch,
    memory_type="explicit_fact"
)

print(f"Létrehozott memóriák: {len(results)}")
```

## Technikai implementáció

### Long-term Memory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY INPUT PROCESSING                      │
│  • Content validation and sanitization                         │
│  • User authorization check                                    │
│  • Memory type classification                                  │
│  • Duplication detection                                       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTENT ENHANCEMENT                          │
│  • Context extraction from source session                      │
│  • Content normalization and cleanup                           │
│  • Metadata enrichment (timestamps, source info)              │
│  • Quality assessment and filtering                            │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EMBEDDING GENERATION                         │
│  • OpenAI text-embedding-3-large                               │
│  • Semantic representation creation                            │
│  • Vector quality validation                                   │
│  • Embedding dimension consistency check                       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DUAL STORAGE PERSISTENCE                     │
│  • PostgreSQL: Memory metadata and content                     │
│  • Qdrant: Vector embeddings for semantic search              │
│  • User-level isolation enforcement                           │
│  • Transactional consistency guarantee                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SEMANTIC SEARCH & RETRIEVAL                 │
│  • Vector similarity search in Qdrant                          │
│  • User-specific memory filtering                              │
│  • Relevance scoring and ranking                               │
│  • Context-aware memory selection                              │
└─────────────────────────────────────────────────────────────────┘
```

### Long-term Memory Service

#### Core Memory Service
```python
class LongTermMemoryService:
    def __init__(self):
        self.db = PostgreSQLMemoryStore()
        self.vector_store = QdrantMemoryStore()
        self.embedder = OpenAIEmbedder()
        self.session_analyzer = SessionSummaryAnalyzer()
        self.deduplicator = MemoryDeduplicator()
    
    async def create_explicit_memory(
        self,
        user_id: int,
        tenant_id: int,
        content: str,
        source_session_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> MemoryCreationResult:
        """
        Create a new explicit fact memory for the user.
        
        Args:
            user_id: User ID for memory ownership
            tenant_id: Tenant ID for isolation
            content: Memory content text
            source_session_id: Optional session reference
            metadata: Additional metadata
            
        Returns:
            MemoryCreationResult with memory ID and status
        """
        
        # Input validation
        await self._validate_memory_input(user_id, tenant_id, content)
        
        # Content processing
        processed_content = await self._process_memory_content(
            content, source_session_id, metadata
        )
        
        # Check for duplicates
        existing_memory = await self.deduplicator.find_similar_memory(
            user_id=user_id,
            content=processed_content,
            similarity_threshold=0.95
        )
        
        if existing_memory:
            log_info(f"Similar memory exists, updating instead of creating new")
            return await self._update_existing_memory(
                existing_memory.id, processed_content
            )
        
        try:
            # Create database record
            memory_id = await self.db.create_long_term_memory(
                user_id=user_id,
                tenant_id=tenant_id,
                content=processed_content,
                memory_type="explicit_fact",
                source_session_id=source_session_id,
                metadata=metadata
            )
            
            # Generate and store embedding
            embedding_result = await self._create_and_store_embedding(
                memory_id=memory_id,
                content=processed_content,
                user_id=user_id,
                memory_type="explicit_fact"
            )
            
            return MemoryCreationResult(
                memory_id=memory_id,
                embedded=embedding_result.success,
                qdrant_point_id=embedding_result.point_id,
                content_length=len(processed_content),
                processing_time_ms=embedding_result.processing_time_ms
            )
            
        except Exception as e:
            # Cleanup on failure
            if 'memory_id' in locals():
                await self._cleanup_failed_memory(memory_id)
            raise MemoryCreationError(f"Failed to create memory: {str(e)}")
    
    async def search_memories(
        self,
        query: str,
        user_id: int,
        memory_type: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.6
    ) -> List[MemorySearchResult]:
        """
        Search user's long-term memories using semantic similarity.
        
        Args:
            query: Search query
            user_id: User ID for memory filtering
            memory_type: Optional memory type filter
            top_k: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of MemorySearchResult objects
        """
        
        # Generate query embedding
        query_embedding = await self.embedder.generate_embedding(query)
        
        # Build search filter
        search_filter = self._build_memory_search_filter(
            user_id=user_id,
            memory_type=memory_type
        )
        
        # Vector search in Qdrant
        search_results = await self.vector_store.search(
            collection_name="long_term_memories",
            query_vector=query_embedding,
            filter=search_filter,
            limit=top_k,
            score_threshold=similarity_threshold
        )
        
        # Convert to structured results
        memories = []
        for hit in search_results:
            memory_data = await self.db.get_memory_by_id(
                hit.payload["memory_id"]
            )
            
            if memory_data:
                memory_result = MemorySearchResult(
                    memory_id=memory_data.id,
                    content=memory_data.content,
                    memory_type=memory_data.memory_type,
                    created_at=memory_data.created_at,
                    similarity_score=hit.score,
                    source_session_id=memory_data.source_session_id,
                    metadata=memory_data.metadata
                )
                memories.append(memory_result)
        
        return memories
    
    async def create_session_summary(
        self,
        session_id: str,
        user_id: int,
        tenant_id: int
    ) -> Optional[MemoryCreationResult]:
        """
        Create automatic session summary memory.
        
        Args:
            session_id: Session to summarize
            user_id: User ID for memory ownership
            tenant_id: Tenant ID for isolation
            
        Returns:
            MemoryCreationResult if summary was created, None if not needed
        """
        
        # Load full conversation
        conversation = await self.db.get_full_conversation(session_id)
        
        if len(conversation) < config.MIN_MESSAGES_FOR_SUMMARY:
            return None  # Too short for meaningful summary
        
        # Generate AI summary
        summary_content = await self.session_analyzer.generate_session_summary(
            conversation=conversation,
            user_context=await self._get_user_context(user_id, tenant_id)
        )
        
        if not summary_content or len(summary_content) < 50:
            return None  # Summary not substantial enough
        
        # Create memory with session summary type
        return await self._create_memory_internal(
            user_id=user_id,
            tenant_id=tenant_id,
            content=summary_content,
            memory_type="session_summary",
            source_session_id=session_id
        )
```

#### Memory Content Processing
```python
class MemoryContentProcessor:
    def __init__(self):
        self.content_normalizer = ContentNormalizer()
        self.context_extractor = ContextExtractor()
    
    async def process_memory_content(
        self,
        raw_content: str,
        source_session_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """Process and enhance memory content for better storage and retrieval."""
        
        # Step 1: Content normalization
        normalized_content = self.content_normalizer.normalize(raw_content)
        
        # Step 2: Context enhancement from session
        if source_session_id:
            session_context = await self.context_extractor.extract_session_context(
                source_session_id
            )
            enhanced_content = self._enhance_with_context(
                normalized_content, session_context
            )
        else:
            enhanced_content = normalized_content
        
        # Step 3: Content validation
        self._validate_processed_content(enhanced_content)
        
        return enhanced_content
    
    def _enhance_with_context(
        self, 
        content: str, 
        session_context: dict
    ) -> str:
        """Add relevant context to make memory more searchable."""
        
        # If content contains pronouns or ambiguous references, add context
        needs_context = self._has_ambiguous_references(content)
        
        if needs_context and session_context.get('entities'):
            # Add entity context to resolve pronouns
            context_additions = []
            
            for entity in session_context['entities']:
                if entity['type'] in ['PERSON', 'ORG', 'PRODUCT']:
                    context_additions.append(f"({entity['text']}: {entity['description']})")
            
            if context_additions:
                enhanced = f"{content} " + " ".join(context_additions)
                return enhanced
        
        return content
    
    def _has_ambiguous_references(self, content: str) -> bool:
        """Detect if content has pronouns or references needing context."""
        
        ambiguous_patterns = [
            r'\b(ő|õ|ez|az|ezt|azt|neki|tőle)\b',  # Hungarian pronouns
            r'\b(he|she|it|this|that|they)\b',      # English pronouns
            r'\b(a cég|a projekt|a rendszer)\b',    # Generic references
        ]
        
        for pattern in ambiguous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
```

#### Session Summary Analysis
```python
class SessionSummaryAnalyzer:
    def __init__(self):
        self.llm_client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    async def generate_session_summary(
        self,
        conversation: List[ChatMessage],
        user_context: UserContext
    ) -> Optional[str]:
        """Generate intelligent summary of conversation session."""
        
        # Filter out system messages and keep only substantial exchanges
        filtered_messages = self._filter_substantial_messages(conversation)
        
        if len(filtered_messages) < 4:
            return None  # Not enough content to summarize
        
        # Build summary prompt
        summary_prompt = self._build_summary_prompt(
            messages=filtered_messages,
            user_language=user_context.language,
            user_name=user_context.name
        )
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="gpt-4o-2024-11-20",
                messages=[
                    {"role": "system", "content": summary_prompt["system"]},
                    {"role": "user", "content": summary_prompt["user"]}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Validate summary quality
            if self._is_summary_substantial(summary, filtered_messages):
                return summary
            else:
                return None
                
        except Exception as e:
            log_error("Session summary generation failed", error=str(e))
            return None
    
    def _build_summary_prompt(
        self,
        messages: List[ChatMessage],
        user_language: str,
        user_name: str
    ) -> dict:
        """Build prompt for session summarization."""
        
        # Format conversation for summarization
        conversation_text = self._format_messages_for_summary(messages)
        
        if user_language == "hu":
            system_prompt = f"""
            Te egy intelligens asszisztens vagy, aki beszélgetések összefoglalóit készíti.
            
            Feladatod: Készíts egy rövid, informatív összefoglalót a beszélgetésről.
            
            Fókuszálj:
            - Fő témák és kérdések
            - Fontos információk és döntések
            - {user_name} preferenciái vagy faktái
            - Jövőbeli referenciához hasznos részletek
            
            Kerüld:
            - Hosszú leírásokat
            - Triviális részleteket
            - Ismétléseket
            
            Maximum 2-3 mondat, tömör és hasznos legyen.
            """
            
            user_prompt = f"""
            Beszélgetés összefoglalása:
            
            {conversation_text}
            
            Készíts összefoglalót magyar nyelven.
            """
        else:
            system_prompt = f"""
            You are an intelligent assistant that creates conversation summaries.
            
            Task: Create a brief, informative summary of this conversation.
            
            Focus on:
            - Main topics and questions discussed
            - Important information and decisions
            - {user_name}'s preferences or facts mentioned
            - Useful details for future reference
            
            Avoid:
            - Verbose descriptions
            - Trivial details
            - Repetition
            
            Maximum 2-3 sentences, concise and useful.
            """
            
            user_prompt = f"""
            Conversation to summarize:
            
            {conversation_text}
            
            Create summary in English.
            """
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }
    
    def _is_summary_substantial(
        self, 
        summary: str, 
        original_messages: List[ChatMessage]
    ) -> bool:
        """Validate that summary contains substantial information."""
        
        # Length check
        if len(summary) < 30:
            return False
        
        # Check for meaningful content (not just generic phrases)
        generic_phrases = [
            "user asked about", "discussed various topics",
            "conversation covered", "beszélgetés során",
            "különböző témák", "általános kérdések"
        ]
        
        summary_lower = summary.lower()
        generic_count = sum(1 for phrase in generic_phrases if phrase in summary_lower)
        
        # Too many generic phrases indicate low-quality summary
        if generic_count > 2:
            return False
        
        # Check if summary contains specific information from conversation
        has_specific_info = self._contains_specific_information(
            summary, original_messages
        )
        
        return has_specific_info
```

#### Memory Deduplication
```python
class MemoryDeduplicator:
    def __init__(self):
        self.similarity_threshold = 0.90  # High threshold for deduplication
        self.embedder = OpenAIEmbedder()
    
    async def find_similar_memory(
        self,
        user_id: int,
        content: str,
        similarity_threshold: Optional[float] = None
    ) -> Optional[Memory]:
        """Find existing memory with very high similarity to avoid duplicates."""
        
        threshold = similarity_threshold or self.similarity_threshold
        
        # Generate embedding for new content
        content_embedding = await self.embedder.generate_embedding(content)
        
        # Search for highly similar memories
        similar_memories = await self.vector_store.search(
            collection_name="long_term_memories",
            query_vector=content_embedding,
            filter={
                "must": [{"key": "user_id", "match": {"value": user_id}}]
            },
            limit=3,
            score_threshold=threshold
        )
        
        if similar_memories:
            # Return the most similar existing memory
            most_similar = similar_memories[0]
            return await self.db.get_memory_by_id(
                most_similar.payload["memory_id"]
            )
        
        return None
    
    async def merge_similar_memories(
        self,
        existing_memory: Memory,
        new_content: str
    ) -> MemoryUpdateResult:
        """Merge new content with existing similar memory."""
        
        # Combine contents intelligently
        merged_content = await self._intelligent_content_merge(
            existing_content=existing_memory.content,
            new_content=new_content
        )
        
        # Update existing memory
        await self.db.update_memory_content(
            memory_id=existing_memory.id,
            new_content=merged_content
        )
        
        # Regenerate embedding for updated content
        new_embedding = await self.embedder.generate_embedding(merged_content)
        await self.vector_store.update_point(
            collection_name="long_term_memories",
            point_id=existing_memory.qdrant_point_id,
            vector=new_embedding,
            payload={"content": merged_content}
        )
        
        return MemoryUpdateResult(
            memory_id=existing_memory.id,
            updated_content=merged_content,
            content_length_change=len(merged_content) - len(existing_memory.content)
        )
```

#### Memory Vector Storage
```python
class QdrantMemoryStore:
    def __init__(self):
        self.client = QdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY
        )
        self.collection_name = "long_term_memories"
    
    async def store_memory_embedding(
        self,
        memory_id: int,
        content: str,
        embedding: List[float],
        user_id: int,
        memory_type: str,
        metadata: Optional[dict] = None
    ) -> str:
        """Store memory embedding in Qdrant with user-specific filtering."""
        
        point_id = str(uuid.uuid4())
        
        # Prepare point payload
        payload = {
            "memory_id": memory_id,
            "user_id": user_id,
            "memory_type": memory_type,
            "content": content,
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        
        # Create point
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        )
        
        # Upsert to Qdrant
        operation_result = await self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        if operation_result.status != UpdateStatus.COMPLETED:
            raise VectorStoreError("Failed to store memory embedding")
        
        return point_id
    
    async def search_user_memories(
        self,
        user_id: int,
        query_vector: List[float],
        memory_type: Optional[str] = None,
        limit: int = 5,
        score_threshold: float = 0.6
    ) -> List[ScoredPoint]:
        """Search memories with user-specific filtering."""
        
        # Build filter for user isolation
        filter_conditions = [
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            )
        ]
        
        if memory_type:
            filter_conditions.append(
                FieldCondition(
                    key="memory_type",
                    match=MatchValue(value=memory_type)
                )
            )
        
        search_filter = Filter(must=filter_conditions)
        
        # Execute search
        search_results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=limit,
            score_threshold=score_threshold
        )
        
        return search_results
```

### Memory Analytics and Insights

#### Memory Usage Analytics
```python
class MemoryAnalytics:
    def __init__(self):
        self.db = PostgreSQLMemoryStore()
    
    async def get_user_memory_stats(self, user_id: int) -> dict:
        """Get comprehensive memory statistics for a user."""
        
        stats = await self.db.get_memory_statistics(user_id)
        
        return {
            "total_memories": stats["total_count"],
            "explicit_facts": stats["explicit_fact_count"],
            "session_summaries": stats["session_summary_count"],
            "average_memory_length": stats["avg_content_length"],
            "oldest_memory": stats["oldest_memory_date"],
            "most_recent_memory": stats["newest_memory_date"],
            "total_content_chars": stats["total_content_length"],
            "memories_created_last_30_days": stats["recent_memory_count"]
        }
    
    async def find_memory_patterns(self, user_id: int) -> dict:
        """Analyze patterns in user's memory creation and usage."""
        
        memories = await self.db.get_all_user_memories(user_id)
        
        # Topic analysis (basic keyword extraction)
        topics = self._extract_common_topics(memories)
        
        # Temporal patterns
        creation_patterns = self._analyze_creation_patterns(memories)
        
        # Content analysis
        content_insights = self._analyze_content_patterns(memories)
        
        return {
            "common_topics": topics,
            "creation_patterns": creation_patterns,
            "content_insights": content_insights
        }
    
    def _extract_common_topics(self, memories: List[Memory]) -> List[dict]:
        """Extract common topics from memory content."""
        
        # Simple keyword frequency analysis
        from collections import Counter
        import re
        
        all_words = []
        for memory in memories:
            # Extract meaningful words (excluding stop words)
            words = re.findall(r'\b[a-záéíóöőüűA-ZÁÉÍÓÖŐÜŰ]{3,}\b', memory.content.lower())
            all_words.extend(words)
        
        # Get top keywords
        word_freq = Counter(all_words)
        
        # Filter out common words (basic stop word removal)
        stop_words = {
            'hogy', 'van', 'egy', 'aki', 'ami', 'ezt', 'azt', 'the', 'and', 'is', 'to'
        }
        
        topics = []
        for word, count in word_freq.most_common(10):
            if word not in stop_words and count > 1:
                topics.append({
                    "keyword": word,
                    "frequency": count,
                    "percentage": round(count / len(memories) * 100, 1)
                })
        
        return topics
```

## Funkció-specifikus konfiguráció

### Memory System Configuration
```ini
# Memory creation settings
MIN_MEMORY_CONTENT_LENGTH=10
MAX_MEMORY_CONTENT_LENGTH=2000
ENABLE_MEMORY_DEDUPLICATION=true
DUPLICATE_SIMILARITY_THRESHOLD=0.90

# Session summary settings
MIN_MESSAGES_FOR_SUMMARY=4
MAX_SUMMARY_LENGTH_CHARS=300
ENABLE_AUTOMATIC_SUMMARIES=true
SUMMARY_GENERATION_TIMEOUT_SEC=30

# Search configuration
DEFAULT_MEMORY_SEARCH_LIMIT=5
MIN_SIMILARITY_THRESHOLD=0.6
MAX_SIMILARITY_THRESHOLD=1.0
ENABLE_FUZZY_MATCHING=true

# Storage settings
MEMORY_EMBEDDING_MODEL=text-embedding-3-large
QDRANT_COLLECTION_NAME=long_term_memories
ENABLE_MEMORY_VERSIONING=false
```

### User-level Memory Isolation
```python
# All memory operations are user-specific
async def create_memory(content: str, user_id: int, tenant_id: int):
    # Memory belongs to specific user
    memory = await db.create_long_term_memory(
        user_id=user_id,        # Required for all operations
        tenant_id=tenant_id,    # For broader tenant analytics
        content=content
    )
    
    # Vector storage with user filter
    await qdrant.store_embedding(
        point_id=str(uuid.uuid4()),
        vector=embedding,
        payload={
            "user_id": user_id,  # Enforced in all searches
            "memory_id": memory.id,
            ...
        }
    )

async def search_memories(query: str, user_id: int):
    # Search only user's memories
    return await qdrant.search(
        query_vector=query_embedding,
        filter={"user_id": user_id}  # Automatic user isolation
    )
```

### Advanced Memory Features

#### Memory Lifecycle Management
```python
class MemoryLifecycleManager:
    async def archive_old_memories(self, user_id: int, days_threshold: int = 365):
        """Archive memories older than threshold to reduce active search space."""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        old_memories = await self.db.get_memories_before_date(
            user_id=user_id,
            cutoff_date=cutoff_date
        )
        
        for memory in old_memories:
            await self.db.mark_memory_archived(memory.id)
            # Optionally move to separate Qdrant collection for archived memories
    
    async def consolidate_similar_memories(self, user_id: int):
        """Periodically consolidate very similar memories to reduce duplication."""
        
        all_memories = await self.db.get_all_user_memories(user_id)
        
        # Find clusters of similar memories
        similarity_clusters = await self._find_similarity_clusters(all_memories)
        
        for cluster in similarity_clusters:
            if len(cluster) > 1:
                # Merge cluster into single consolidated memory
                consolidated = await self._merge_memory_cluster(cluster)
                await self._replace_cluster_with_consolidated(cluster, consolidated)
```

#### Smart Memory Suggestions
```python
class MemorySuggestionEngine:
    async def suggest_memories_for_query(
        self, 
        query: str, 
        user_id: int,
        conversation_context: List[ChatMessage]
    ) -> List[MemorySuggestion]:
        """Suggest relevant memories based on current query and conversation."""
        
        # Enhanced query with conversation context
        enhanced_query = self._enhance_query_with_context(query, conversation_context)
        
        # Search memories with relaxed threshold for suggestions
        candidate_memories = await self.memory_service.search_memories(
            query=enhanced_query,
            user_id=user_id,
            top_k=10,
            similarity_threshold=0.4  # Lower threshold for suggestions
        )
        
        # Score and rank suggestions
        suggestions = []
        for memory in candidate_memories:
            relevance_score = self._calculate_contextual_relevance(
                memory=memory,
                query=query,
                conversation_context=conversation_context
            )
            
            if relevance_score > 0.5:
                suggestions.append(MemorySuggestion(
                    memory=memory,
                    relevance_score=relevance_score,
                    suggestion_reason=self._explain_suggestion(memory, query)
                ))
        
        # Return top suggestions
        return sorted(suggestions, key=lambda x: x.relevance_score, reverse=True)[:3]
```

#### Memory Quality Assessment
```python
def assess_memory_quality(memory: Memory) -> float:
    """Assess the quality and usefulness of a memory entry."""
    
    quality_score = 1.0
    content = memory.content
    
    # Content length assessment
    if len(content) < 20:
        quality_score *= 0.5  # Very short memories are less useful
    elif len(content) > 500:
        quality_score *= 0.8  # Very long memories might be too general
    
    # Specificity assessment
    specific_indicators = ['dátum', 'date', 'név', 'name', 'szám', 'number', '$', '€']
    if any(indicator in content.lower() for indicator in specific_indicators):
        quality_score *= 1.2  # Specific information is valuable
    
    # Vague language penalty
    vague_phrases = ['valami', 'something', 'általában', 'usually', 'talán', 'maybe']
    vague_count = sum(1 for phrase in vague_phrases if phrase in content.lower())
    if vague_count > 0:
        quality_score *= (1.0 - vague_count * 0.1)
    
    # Recency bonus (more recent memories might be more relevant)
    if memory.created_at:
        days_old = (datetime.utcnow() - memory.created_at).days
        if days_old < 30:
            quality_score *= 1.1
        elif days_old > 365:
            quality_score *= 0.9
    
    return min(1.0, max(0.1, quality_score))
```