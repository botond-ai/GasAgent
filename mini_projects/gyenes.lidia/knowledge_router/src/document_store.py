import json
import os
from typing import List
from dataclasses import dataclass
from dotenv import load_dotenv

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document as LangchainDocument

load_dotenv()

@dataclass
class KnowledgeDoc:
    id: int
    title: str
    content: str
    category: str

class VectorStore:
    def __init__(self, db_path: str, vector_db_dir: str = "./chroma_db"):
        self.db_path = db_path
        self.vector_db_dir = vector_db_dir
        self.vector_db = None
        self.embeddings = None

        # 1. Megpróbáljuk betölteni az OpenAI-t
        try:
            self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        except Exception:
            print("⚠️ Nincs OpenAI driver.")

        # Csak akkor folytatjuk, ha van driver, de itt is elkapjuk a hibát
        if self.embeddings:
            try:
                self._initialize_db()
            except Exception as e:
                print(f"\n⚠️ RAG HIBA: Nem sikerült elérni az OpenAI-t (Quota/Net hiba).")
                print(f"   Részletek: {e}")
                print("   ➡️ A program RAG nélkül, csak Weather módban indul tovább.\n")
                self.vector_db = None # Kikapcsoljuk a RAG-ot

    def _initialize_db(self):
        if os.path.exists(self.vector_db_dir) and os.path.isdir(self.vector_db_dir):
            try:
                self.vector_db = Chroma(persist_directory=self.vector_db_dir, embedding_function=self.embeddings)
                if self.vector_db._collection.count() > 0:
                    print("✅ Meglévő vektor DB betöltve.")
                    return
            except:
                pass 

        print("🔄 Vektor adatbázis építése...")
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except FileNotFoundError:
            return

        documents = []
        for item in raw_data:
            meta = {"id": item['id'], "title": item['title'], "category": item['category']}
            doc = LangchainDocument(page_content=item['content'], metadata=meta)
            documents.append(doc)

        # ITT SZÁLLT EL EDDIG -> Most elkapjuk a hibát a __init__-ben
        self.vector_db = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=self.vector_db_dir
        )
        print(f"✅ Vektor DB kész! ({len(documents)} doksi)")

    def similarity_search(self, query: str, k: int = 2) -> List[KnowledgeDoc]:
        if not self.vector_db:
            return []
        try:
            results = self.vector_db.similarity_search(query, k=k)
            return [KnowledgeDoc(res.metadata['id'], res.metadata['title'], res.metadata['category'], res.page_content) for res in results]
        except:
            return []