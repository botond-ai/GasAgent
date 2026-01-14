# MeetingAI - RAG Agent Project

## Implementált funkciók (HW2)
- **Vector Database**: FAISS (Facebook AI Similarity Search) a gyors kereséshez.
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` modell a szövegek számszerűsítéséhez.
- **Document Retrieval**: A rendszer nem a teljes szöveget küldi az LLM-nek, hanem csak a releváns részeket keresi ki.
- **RAG Workflow**: 
  1. Szöveg darabolása (Chunking)
  2. Vektorizálás (Embedding)
  3. Releváns részek kikeresése (Retrieval)
  4. Válaszgenerálás az LM Studio-n keresztül (Generation)


Az `apikulcs.env` fájlban állítsa be az `OPENAI_BASE_URL`-t az LM Studio címére.
Futtatás: `python run_agent.py notes.txt`