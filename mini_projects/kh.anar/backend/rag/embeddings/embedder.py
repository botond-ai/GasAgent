"""Beágyazó interfész és determinisztikus tesztbeágyazó.

A valódi beágyazó egy sentence-transformers vagy OpenAI embeddings modellhez
hívna. Teszt-determinizmusért egy HashEmbeddert adunk, ami a szöveget
fix hosszúságú pszeudo-beágyazássá alakítja egy hash függvényből.
"""
from typing import List
import hashlib


class Embedder:
    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts. Default implementation calls embed_text for each."""
        return [self.embed_text(t) for t in texts]


class HashEmbedder(Embedder):
    def __init__(self, dim: int = 32):
        self.dim = dim

    def embed_text(self, text: str) -> List[float]:
        # determinisztikus pszeudo-beágyazás: sha256, majd dim darab float-ra bontás
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vals = [b for b in h]
        # ismétlés/vágás a dim méretre
        rep = (vals * ((self.dim // len(vals)) + 1))[: self.dim]
        # normalizálás 0-1 közé
        emb = [v / 255.0 for v in rep]
        return emb
