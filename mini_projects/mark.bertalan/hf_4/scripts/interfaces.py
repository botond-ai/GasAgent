
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Literal, Dict, Any


class Embedder(ABC):

    @abstractmethod
    def get_embedding(
        self,
        text: str,
    ) -> List[Tuple[str, List[float]]]:
        """
        Transform the given text to vector embeddings (chunked).

        Args:
            text: Input text.

        Returns:
            List of (chunk_text, embedding_vector) tuples.
        """
        pass


class VectorDB(ABC):

    @abstractmethod
    def add(self, id: str, text: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Persist the given text and embedded vector into the vector database.

        Args:
            id: Unique id.
            text: Text chunk.
            embedding: The vector which represents the text.
            metadata: Optional metadata to store with the vector (e.g., source document, chunk index).
        """
        pass

    @abstractmethod
    def similarity_search(
            self,
            embedding: List[float],
            k: int = 3
    ) -> List[Tuple[str, float, float, str, Optional[Dict[str, Any]]]]:
        """
        Find the k most similar entries to the given embedding.

        Args:
            embedding: The query embedding vector.
            k: Number of nearest neighbors to return.

        Returns:
            List of tuples (id, distance, similarity, text, metadata) ordered by similarity.
            Distance is the cosine distance (lower is better).
            Similarity is cosine similarity (higher is better, range 0-1).
            Metadata is optional dict containing chunk information.
        """
        pass

    @abstractmethod
    def knn_search(
            self,
            embedding: List[float],
            k: int = 3
    ) -> List[Tuple[str, float, str, Optional[Dict[str, Any]]]]:
        """
        Find the k nearest neighbors using Euclidean distance.

        Args:
            embedding: The query embedding vector.
            k: Number of nearest neighbors to return.

        Returns:
            List of tuples (id, euclidean_distance, text, metadata) ordered by distance.
            Lower distance means higher similarity.
            Metadata is optional dict containing chunk information.
        """
        pass


class LLM(ABC):
    """Abstract interface for Large Language Model text generation."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        context: List[str],
        max_tokens: int = 500,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate a response based on the prompt and retrieved context.

        Args:
            prompt: The user's question or query.
            context: List of relevant document chunks retrieved from vector search.
            max_tokens: Maximum number of tokens to generate.
            conversation_history: Optional list of previous messages [{"role": "user/assistant", "content": "..."}].

        Returns:
            Generated response text from the LLM.
        """
        pass
