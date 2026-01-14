import os
import math
import json
from typing import List, Dict, Any, Optional
import numpy as np
import httpx
from dotenv import load_dotenv
from openai import OpenAI

# Load environment (allows using apikulcs.env if present and mapped to .env by user)
load_dotenv()
# Instantiate OpenAI client (supports LM Studio via OPENAI_BASE_URL)
_openai_client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)


class OpenAIEmbeddingsClient:
    def __init__(self, api_key: Optional[str] = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        # Use OpenAI python client (works with LM Studio via base_url)
        resp = _openai_client.embeddings.create(model=self.model, input=texts)
        # resp may be dict-like or object-like; normalize
        items = None
        try:
            items = resp.data
        except Exception:
            items = resp.get("data", [])
        embeddings = []
        for item in items:
            emb = None
            if hasattr(item, "embedding"):
                emb = item.embedding
            elif isinstance(item, dict):
                emb = item.get("embedding")
            if emb is not None:
                embeddings.append(list(emb))
        return embeddings


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class SimpleVectorStore:
    """In-memory vector store with optional persistence.

    Stores: list of vectors and parallel list of documents (dict with 'text' and 'meta').
    """

    def __init__(self):
        self.vectors: List[np.ndarray] = []
        self.docs: List[Dict[str, Any]] = []

    def add(self, vectors: List[List[float]], docs: List[Dict[str, Any]]):
        for v, d in zip(vectors, docs):
            self.vectors.append(np.array(v, dtype=float))
            self.docs.append(d)

    def search(self, query_vector: List[float], k: int = 3) -> List[Dict[str, Any]]:
        if not self.vectors:
            return []
        q = np.array(query_vector, dtype=float)
        scores = [(_cosine(q, v), idx) for idx, v in enumerate(self.vectors)]
        scores.sort(reverse=True, key=lambda x: x[0])
        top = scores[:k]
        return [ {"score": float(s), "doc": self.docs[i]} for s,i in top]

    def persist(self, path: str):
        # Save docs and vectors as lists
        data = {"docs": self.docs, "vectors": [v.tolist() for v in self.vectors]}
        with open(path, "w", encoding="utf8") as f:
            json.dump(data, f)

    def load(self, path: str):
        with open(path, "r", encoding="utf8") as f:
            data = json.load(f)
        self.docs = data.get("docs", [])
        self.vectors = [np.array(v, dtype=float) for v in data.get("vectors", [])]


class Retriever:
    def __init__(self, embed_client: OpenAIEmbeddingsClient, store: SimpleVectorStore):
        self.embed_client = embed_client
        self.store = store

    async def retrieve(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        emb = await self.embed_client.embed([query])
        if not emb:
            return []
        return self.store.search(emb[0], k=k)


class RAGAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.embed_client = OpenAIEmbeddingsClient(api_key=self.api_key)
        self.store = SimpleVectorStore()
        self.retriever = Retriever(self.embed_client, self.store)

    async def add_documents(self, texts: List[str], metas: Optional[List[Dict[str, Any]]] = None):
        metas = metas or [{} for _ in texts]
        embeddings = await self.embed_client.embed(texts)
        docs = [{"text": t, "meta": m} for t,m in zip(texts, metas)]
        self.store.add(embeddings, docs)

    async def answer(self, query: str, k: int = 3) -> Dict[str, Any]:
        # Retrieve
        hits = await self.retriever.retrieve(query, k=k)
        contexts = [h["doc"]["text"] if isinstance(h.get("doc"), dict) else h["doc"] for h in hits]
        # Build prompt
        system = "You are a helpful assistant that answers questions using the provided context snippets. If the answer is not in the context, say you don't know."
        context_text = "\n\n---\n\n".join(contexts) if contexts else ""
        user_prompt = f"Use the following context to answer the question. Context:\n{context_text}\n\nQuestion: {query}\nAnswer concisely."

        # Call OpenAI Chat completion
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set for generation")
        # Use OpenAI python client for chat completion
        resp = _openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
            max_tokens=256,
            temperature=0.0,
        )
        data = None
        try:
            data = resp
            # try object-like access
            text_out = resp.choices[0].message.content
        except Exception:
            try:
                data = resp if isinstance(resp, dict) else dict(resp)
                text_out = data.get("choices", [])[0].get("message", {}).get("content", "")
            except Exception:
                text_out = ""

        return {"query": query, "retrieved": hits, "answer": text_out, "raw": data}
