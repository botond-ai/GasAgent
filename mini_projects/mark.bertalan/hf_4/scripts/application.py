"""
Orchestrator for embedding-based query processing.

This module coordinates embedding generation and vector storage operations
while adhering to dependency inversion principles through abstract interfaces.
"""

import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from scripts.interfaces import Embedder, VectorDB, LLM


class EmbeddingApp:
    """
    Manages the complete workflow for text query processing using embeddings.

    Responsibilities:
    - Coordinate embedding generation through injected services
    - Manage vector storage operations
    - Execute similarity searches across multiple algorithms

    Architecture follows the Open/Closed Principle: extensible through
    different implementations of Embedder and VectorDB without
    modifying this orchestrator.
    """

    def __init__(self, embedding_service: Embedder, vector_store: VectorDB, llm: Optional[LLM] = None, config=None):
        """
        Construct processor with dependency-injected components.

        Args:
            embedding_service: Component responsible for text-to-vector transformation
            vector_store: Component handling vector persistence and retrieval
            llm: Optional LLM component for RAG text generation
            config: Optional Config object (for Jira integration)
        """
        self._embedder = embedding_service
        self._vector_db = vector_store
        self._llm = llm
        self._config = config
        self._query_graph = None  # Lazy-loaded LangGraph
        self._conversation_history = []  # Track conversation across queries
        self._pending_jira_suggestion = None  # Track pending Jira ticket suggestion

    def _get_query_graph(self):
        """Lazy-load compiled LangGraph."""
        if self._query_graph is None:
            from scripts.graph.rag_graph import create_rag_graph
            self._query_graph = create_rag_graph(
                self._embedder,
                self._vector_db,
                self._llm,
                self._config,  # Pass config for Jira integration
                self._config   # Pass config for Teams integration (same config object)
            )
        return self._query_graph

    def reset_conversation(self):
        """Clear conversation history."""
        self._conversation_history = []

    def create_jira_ticket(self, department: str, summary: str, description: str, priority: str) -> Tuple[str, str]:
        """
        Create a Jira ticket with the provided details.

        Args:
            department: Department name (hr, dev, support, management)
            summary: Ticket title
            description: Ticket description
            priority: Priority level (High, Medium, Low)

        Returns:
            Tuple of (task_key, task_url) or raises exception on failure
        """
        from scripts.graph.nodes.jira_create import create_jira_task_node

        # Create minimal state for Jira creation
        state = {
            "jira_department": department,
            "jira_summary": summary,
            "jira_description": description,
            "jira_priority": priority,
            "errors": [],
            "step_timings": {}
        }

        # Call the Jira creation node
        result_state = create_jira_task_node(state)

        # Check for errors
        if result_state.get("errors"):
            raise Exception(f"Jira creation failed: {result_state['errors']}")

        # Return task details
        task_key = result_state.get("jira_task_key", "")
        task_url = result_state.get("jira_task_url", "")

        return task_key, task_url

    def _parse_domains_config(self) -> List[str]:
        """
        Extract domain list from environment configuration.

        Returns:
            List of domain identifiers from DOMAINS env variable
        """
        domains_config = os.getenv("DOMAINS", "hr,dev,support,management")
        return [domain.strip() for domain in domains_config.split(",") if domain.strip()]

    def _normalize_markdown_content(self, content: str) -> str:
        """
        Clean and normalize markdown text for processing.

        Args:
            content: Raw markdown string

        Returns:
            Normalized text with consolidated whitespace
        """
        return re.sub(r"\s+\n", "\n", content).strip()

    def _load_domain_documents(self, base_path: Path, domain: str) -> List[str]:
        """
        Load all markdown documents from a specific domain directory.

        Args:
            base_path: Root directory containing domain folders
            domain: Domain identifier

        Returns:
            List of markdown file contents
        """
        domain_path = base_path / domain
        if not domain_path.exists():
            return []

        documents = []
        for markdown_file in sorted(domain_path.glob("*.md")):
            raw_content = markdown_file.read_text(encoding="utf-8", errors="ignore")
            normalized = self._normalize_markdown_content(raw_content)
            documents.append(normalized)

        return documents

    def _store_document(self, document_text: str, source_doc_id: str, domain: str) -> None:
        """
        Generate embeddings for document chunks and persist to vector store.

        Args:
            document_text: Preprocessed document content
            source_doc_id: ID of the source document (for tracking chunks)
            domain: Domain name (e.g., 'hr', 'dev')
        """
        # Get list of (chunk_text, embedding_vector) tuples
        chunk_embeddings = self._embedder.get_embedding(document_text)

        # Store each chunk separately with metadata
        for chunk_idx, (chunk_text, embedding_vector) in enumerate(chunk_embeddings):
            chunk_id = f"{source_doc_id}_chunk_{chunk_idx}"
            metadata = {
                "source_document_id": source_doc_id,
                "chunk_index": chunk_idx,
                "total_chunks": len(chunk_embeddings),
                "domain": domain,
            }
            self._vector_db.add(chunk_id, chunk_text, embedding_vector, metadata)

    def store_and_embed_documents(self, root_dir: Path) -> None:
        """
        Process and store all documents from configured domains.

        Iterates through domain directories, loads markdown files,
        generates embeddings, and persists to vector database.

        Args:
            root_dir: Base directory containing domain subdirectories
        """
        configured_domains = self._parse_domains_config()

        for domain_name in configured_domains:
            domain_path = root_dir / domain_name
            if not domain_path.exists():
                continue

            # Process each markdown file in the domain
            for markdown_file in sorted(domain_path.glob("*.md")):
                # Generate unique document ID from file path
                source_doc_id = f"{domain_name}_{markdown_file.stem}"

                # Load and normalize document
                raw_content = markdown_file.read_text(encoding="utf-8", errors="ignore")
                normalized_content = self._normalize_markdown_content(raw_content)

                # Store document with metadata
                print(f"Processing: {markdown_file.name} (domain: {domain_name})")
                self._store_document(normalized_content, source_doc_id, domain_name)

    def process_query(self, text: str, k: int = 3) -> Tuple[str, Dict[str, List]]:
        """
        Execute full query processing pipeline.

        Generates embedding for input query and performs similarity
        searches using both cosine similarity and KNN algorithms.

        Args:
            text: User's search query
            k: Number of results to return per search method

        Returns:
            Tuple containing (query_identifier, search_results_dict)
            where search_results_dict has 'cosine' and 'knn' keys
        """
        query_identifier = str(uuid.uuid4())

        # get_embedding returns list of (chunk_text, embedding) tuples
        # For queries, we just use the first chunk's embedding
        chunk_embeddings = self._embedder.get_embedding(text)
        query_vector = chunk_embeddings[0][1]  # Get the embedding from first tuple

        cosine_matches = self._vector_db.similarity_search(query_vector, k=k)
        knn_matches = self._vector_db.knn_search(query_vector, k=k)

        search_results = {
            'cosine': cosine_matches,
            'knn': knn_matches
        }

        return query_identifier, search_results

    def process_query_with_rag(
        self,
        text: str,
        k: int = 3,
        max_tokens: int = 500
    ) -> Tuple[str, Dict[str, List], str]:
        """
        Execute RAG pipeline using LangGraph with conversation history.

        Args:
            text: User's question or query.
            k: Number of documents to retrieve for context.
            max_tokens: Maximum tokens for LLM response generation.

        Returns:
            Tuple containing (query_id, search_results, generated_answer)

        Raises:
            ValueError: If LLM was not provided during initialization.
        """
        if self._llm is None:
            raise ValueError(
                "LLM component not initialized. "
                "Please provide an LLM instance when creating EmbeddingApp."
            )

        # Get compiled graph
        graph = self._get_query_graph()

        # Initialize state with conversation history and pending Jira suggestion
        initial_state = {
            "query": text,
            "k": k,
            "max_tokens": max_tokens,
            "skip_llm": False,
            "conversation_history": self._conversation_history.copy(),
            "pending_jira_suggestion": self._pending_jira_suggestion,  # Pass pending suggestion
            "step_timings": {},
            "errors": []
        }

        # Execute graph
        final_state = graph.invoke(initial_state)

        # Check for errors
        if final_state.get("errors"):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Errors during execution: {final_state['errors']}")

        # Update conversation history for next query
        self._conversation_history = final_state.get("conversation_history", [])
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"===== Application: Updated conversation history: {len(self._conversation_history)} messages =====")

        # Store pending Jira suggestion if suggested
        if final_state.get("jira_suggested", False):
            self._pending_jira_suggestion = {
                "department": final_state.get("jira_department", "support"),
                "summary": final_state.get("jira_summary", ""),
                "description": final_state.get("jira_description", ""),
                "priority": final_state.get("jira_priority", "Medium")
            }
            logger.info(f"===== Application: Stored pending Jira suggestion: {self._pending_jira_suggestion} =====")
        else:
            self._pending_jira_suggestion = None
            logger.info("===== Application: No Jira suggestion this turn =====")

        # Return results with state (for Jira suggestion)
        # Handle case where we went through Jira confirmation path (no search results)
        search_results = {
            "cosine": final_state.get("cosine_results", []),
            "knn": final_state.get("knn_results", [])
        }

        return final_state.get("query_id", "jira-confirmation"), search_results, final_state.get("generated_answer", ""), final_state
