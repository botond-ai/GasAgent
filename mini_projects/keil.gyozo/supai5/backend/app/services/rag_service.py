"""
RAG (Retrieval-Augmented Generation) service with query expansion and reranking.
"""
from typing import Optional
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.logging import get_logger
from app.services.qdrant_service import QdrantService
from app.services.redis_service import RedisService

logger = get_logger(__name__)


class RAGService:
    """Service for RAG pipeline operations."""

    def __init__(
        self,
        qdrant_service: QdrantService,
        redis_service: RedisService
    ):
        """
        Initialize RAG service.

        Args:
            qdrant_service: Qdrant vector database service
            redis_service: Redis cache service
        """
        self.qdrant = qdrant_service
        self.redis = redis_service

        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key
        )

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key
        )

        logger.info("Initialized RAGService")

    async def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding with caching.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Check cache
        cached = self.redis.get_embedding(text)
        if cached:
            return cached

        # Generate embedding
        embedding = await self.embeddings.aembed_query(text)

        # Cache result
        self.redis.set_embedding(text, embedding)

        return embedding

    async def expand_queries(self, original_query: str) -> list[str]:
        """
        Generate semantic query variations.

        Args:
            original_query: Original customer query

        Returns:
            List of query variations including original
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a query expansion expert. Generate {count} semantic variations
            of the user's support question. Each variation should:
            - Capture the same core intent
            - Use different phrasing or terminology
            - Help retrieve relevant knowledge base articles

            Return ONLY the variations, one per line, without numbering."""),
            ("user", "{query}")
        ])

        chain = prompt | self.llm

        response = await chain.ainvoke({
            "query": original_query,
            "count": settings.query_expansion_count - 1  # -1 because we'll add original
        })

        variations = [line.strip() for line in response.content.strip().split('\n') if line.strip()]

        # Always include original query first
        queries = [original_query] + variations[:settings.query_expansion_count - 1]

        logger.info(f"Expanded query into {len(queries)} variations")
        return queries

    async def search_documents(
        self,
        queries: list[str],
        category_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Hybrid search across multiple queries.

        Args:
            queries: List of query strings
            category_filter: Optional category filter

        Returns:
            Deduplicated list of retrieved documents
        """
        all_results = []
        seen_doc_ids = set()

        for query in queries:
            # Get embedding
            logger.info(f"Getting embedding for query: {query[:50]}...")
            try:
                embedding = await self.get_embedding(query)
                logger.info(f"Embedding generated, length: {len(embedding)}")
            except Exception as e:
                logger.error(f"Error getting embedding: {e}")
                continue

            # Search Qdrant - ADDED AWAIT HERE
            logger.info(f"Calling Qdrant search...")
            results = await self.qdrant.search(
                query_vector=embedding,
                limit=settings.top_k_retrieval,
                score_threshold=settings.score_threshold,
                filter_category=category_filter
            )

            # Deduplicate by doc_id
            for result in results:
                doc_id = result.get("doc_id")
                if doc_id not in seen_doc_ids:
                    all_results.append(result)
                    seen_doc_ids.add(doc_id)

        logger.info(f"Retrieved {len(all_results)} unique documents from {len(queries)} queries")
        if not all_results:
            logger.warning(f"No documents found! Queries used: {queries}")
        return all_results

    async def rerank_documents(
        self,
        query: str,
        documents: list[dict]
    ) -> list[dict]:
        """
        Rerank documents using LLM-based scoring.

        Args:
            query: Original query
            documents: List of retrieved documents

        Returns:
            Reranked and filtered documents
        """
        if not documents:
            return []

        # Use Cohere reranking if API key available
        if settings.cohere_api_key:
            return await self._rerank_with_cohere(query, documents)

        # Fallback to LLM-based reranking
        return await self._rerank_with_llm(query, documents)

    async def _rerank_with_cohere(self, query: str, documents: list[dict]) -> list[dict]:
        """Rerank using Cohere Rerank API."""
        try:
            import cohere
            co = cohere.Client(settings.cohere_api_key)

            # Prepare documents for reranking
            texts = [doc["text"] for doc in documents]

            # Rerank
            results = co.rerank(
                query=query,
                documents=texts,
                top_n=settings.top_k_rerank,
                model="rerank-english-v3.0"
            )

            # Map back to original documents with new scores
            reranked = []
            for result in results.results:
                doc = documents[result.index].copy()
                doc["rerank_score"] = result.relevance_score
                reranked.append(doc)

            logger.info(f"Reranked to {len(reranked)} documents using Cohere")
            return reranked

        except Exception as e:
            logger.warning(f"Cohere reranking failed: {e}, falling back to LLM")
            return await self._rerank_with_llm(query, documents)

    async def _rerank_with_llm(self, query: str, documents: list[dict]) -> list[dict]:
        """Rerank using LLM-based scoring."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a relevance scoring expert. Rate each document's relevance
            to the query on a scale of 0-10. Return ONLY a JSON array of scores.

            Example: [8, 6, 9, 3, 7]"""),
            ("user", """Query: {query}

            Documents:
            {documents}""")
        ])

        # Format documents
        doc_texts = "\n\n".join([
            f"[{i}] {doc['text'][:500]}"
            for i, doc in enumerate(documents)
        ])

        chain = prompt | self.llm

        try:
            response = await chain.ainvoke({
                "query": query,
                "documents": doc_texts
            })

            # Parse scores
            import json
            scores = json.loads(response.content.strip())

            # Combine documents with scores
            scored_docs = [
                {**doc, "rerank_score": score / 10.0}
                for doc, score in zip(documents, scores)
            ]

            # Sort by score and take top K
            scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
            reranked = scored_docs[:settings.top_k_rerank]

            logger.info(f"Reranked to {len(reranked)} documents using LLM")
            return reranked

        except Exception as e:
            logger.error(f"LLM reranking failed: {e}")
            # Return top documents by original score
            return sorted(documents, key=lambda x: x["score"], reverse=True)[:settings.top_k_rerank]

    async def retrieve(
        self,
        query: str,
        category_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Complete RAG retrieval pipeline.

        Args:
            query: Customer query
            category_filter: Optional category filter

        Returns:
            Reranked relevant documents
        """
        # 1. Expand queries
        queries = await self.expand_queries(query)

        # 2. Search documents
        documents = await self.search_documents(queries, category_filter)

        # 3. Rerank
        reranked = await self.rerank_documents(query, documents)

        logger.info(f"RAG pipeline complete: {len(reranked)} final documents")
        return reranked