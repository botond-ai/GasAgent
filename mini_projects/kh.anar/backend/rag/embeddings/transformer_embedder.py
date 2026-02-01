"""Transformer-alapú beágyazó, amely sentence-transformers-t használ, ha elérhető.

Ha nincs telepítve a transformer csomag, HashEmbedderre lép vissza; ez gyors és
determinisztikus teszteket biztosít, miközben élesben jobb minőségű beágyazást tesz lehetővé,
ha a függőség jelen van.
"""
from typing import List
from .embedder import Embedder, HashEmbedder

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


class TransformerEmbedder(Embedder):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers not installed")
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> List[float]:
        vec = self.model.encode(text)
        return vec.tolist()


class FallbackEmbedder(HashEmbedder):
    """Álnév a HashEmbedder használatához, amikor a valódi modell nem elérhető."""
    pass
