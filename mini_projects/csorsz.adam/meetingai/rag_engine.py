import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class SimpleRAG:
    def __init__(self):
        # Ez a modell kicsi és gyors, lefut a gépeden
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.chunks = []
        self.embeddings = []

    def add_documents(self, text: str):
        # Feldaraboljuk a szöveget mondatonként vagy bekezdésenként
        self.chunks = [c.strip() for c in text.split('\n') if len(c.strip()) > 10]
        if self.chunks:
            self.embeddings = self.model.encode(self.chunks)

    def search(self, query: str, top_k: int = 2):
        if not self.chunks:
            return ""
        
        query_embedding = self.model.encode([query])
        # Megkeressük a leginkább hasonló részeket
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        relevant_parts = [self.chunks[i] for i in top_indices]
        return "\n".join(relevant_parts)