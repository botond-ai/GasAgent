MeetingAI RAG mini

This module contains a minimal RAG pipeline:

- `OpenAIEmbeddingsClient` — async wrapper for OpenAI Embeddings API.
- `SimpleVectorStore` — in-memory vector store with cosine retrieval and optional persist/load.
- `Retriever` — retrieves top-k documents for a query.
- `RAGAgent` — helper to add documents and answer queries using retrieved contexts and OpenAI Chat completions.

Usage (quick):

1. Ensure `OPENAI_API_KEY` is available (or set in `apikulcs.env`).
2. In python async code:

```py
from meetingai.rag import RAGAgent
import asyncio

async def demo():
    agent = RAGAgent()
    await agent.add_documents(["Decisions: We will use X.", "The team agreed to deliver by Friday."])
    res = await agent.answer("What was decided about delivery?")
    print(res["answer"]) 

asyncio.run(demo())
```

This is a simple, local demo — for production use replace the vector store with a DB (Chroma/FAISS/Pinecone) and add batching, error handling and robust prompt engineering.
