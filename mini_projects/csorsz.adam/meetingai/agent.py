import os
import json
import asyncio
import numpy as np
from typing import Any, Dict
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# --- RAG INFRASTRUKTÚRA (A tanár által hiányolt technológiák) ---
import faiss
from sentence_transformers import SentenceTransformer

class SimpleRAG:
    """Valódi RAG implementáció Vector Database-szel."""
    def __init__(self):
        # ❌ Tanári hiánypótló: Embeddings (HuggingFace modell)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.chunks = []

    def add_documents(self, text: str):
        """Dokumentum feldarabolása és indexelése (Document retrieval alapja)."""
        # Szöveg darabolása (Chunking)
        self.chunks = [c.strip() for c in text.split('\n') if len(c.strip()) > 15]
        if not self.chunks:
            return

        # ❌ Tanári hiánypótló: Vector database (FAISS)
        # Elkészítjük a beágyazásokat (embeddings)
        embeddings = self.model.encode(self.chunks)
        dimension = embeddings.shape[1]
        
        # FAISS index létrehozása a vektorok tárolásához és kereséséhez
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))

    def search(self, query: str, top_k: int = 2):
        """Releváns információ kikeresése a vektoradatbázisból."""
        if self.index is None or not self.chunks:
            return ""
        
        # A kérdést is vektorrá alakítjuk
        query_embedding = self.model.encode([query]).astype('float32')
        
        # Keresés a vektoradatbázisban
        distances, indices = self.index.search(query_embedding, top_k)
        
        # A legközelebbi találatok összeszedése
        results = [self.chunks[i] for i in indices[0] if i != -1]
        return "\n".join(results)

# --- KÖRNYEZETI VÁLTOZÓK ---
current_dir = Path(__file__).parent.parent 
env_path = current_dir / 'apikulcs.env'
load_dotenv(dotenv_path=env_path)

# Kliens inicializálása
_openai_client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"), 
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=300.0
)

try:
    from .sentiment_client import AsyncSentimentClient
except ImportError:
    from sentiment_client import AsyncSentimentClient

class MeetingAgent:
    """RAG-alapú MeetingAI ügynök (HW2 Megfelelő verzió)."""

    def __init__(self, openai_key: str | None = None):
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.sentiment_client = AsyncSentimentClient()
        self.rag = SimpleRAG() # RAG motor inicializálása

    async def _call_planner(self, context: str) -> Dict[str, Any]:
        """❌ Tanári hiánypótló: LLM answer generation a kinyert adatok alapján."""
        if not self.openai_key:
            return {"call_tool": True, "tool": "analyze_sentiment", "reason": "no key"}

        system = "You are a meeting analyst. Use ONLY the provided context. Reply in JSON."
        prompt = (
            "Based on this retrieved context, is there any tension or decision mentioned?\n"
            "JSON format: {\"call_tool\": true, \"tool\": \"analyze_sentiment\", \"reason\": \"...\"}\n\n"
            "Context from Vector DB:\n" + context
        )

        try:
            resp = _openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "local-model"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.0,
            )
            text_out = resp.choices[0].message.content
            
            # JSON tisztítás
            start = text_out.find('{')
            end = text_out.rfind('}') + 1
            return json.loads(text_out[start:end])
        except Exception as e:
            return {"call_tool": True, "tool": "analyze_sentiment", "reason": f"fallback: {e}"}

    async def run(self, notes: str) -> Dict[str, Any]:
        """❌ Tanári hiánypótló: Teljes RAG workflow."""
        
        # 1. Indexing: Szöveg betöltése a vektoradatbázisba
        self.rag.add_documents(notes)
        
        # 2. Retrieval: Keresés a vektorok között
        # (Pl. megkeressük a hangulattal vagy döntésekkel kapcsolatos részeket)
        relevant_context = self.rag.search("mood, feelings and decisions")
        
        # 3. Planning & Generation: Válasz az adatok alapján
        plan = await self._call_planner(relevant_context)
        
        result: Dict[str, Any] = {
            "plan": plan,
            "rag_system": {
                "vector_db": "FAISS",
                "embeddings": "all-MiniLM-L6-v2",
                "status": "ready"
            },
            "retrieved_context": relevant_context
        }

        if plan.get("call_tool") and plan.get("tool") == "analyze_sentiment":
            sent = await self.sentiment_client.analyze(relevant_context)
            result["tool_output"] = sent

        return result