# AI Internal Knowledge Router - Fejlesztési Terv

Ezt a projektet választottam kidolgozásra. A cél egy intelligens vállalati tudásirányító ágens létrehozása LangGraph segítségével.

## Tervezett mérföldkövek:
1. **Router Logika:** Intent felismerés (HR vs IT vs Legal).
2. **RAG Implementáció:** Egy választott domain (pl. HR) tudásbázisának beépítése.
3. **Multi-Vector Store:** A logika kiterjesztése több témakörre.
4. **Workflow Automatizáció:** Mockolt API hívások (Jira, File creation).

## Tech Stack:
- Python
- LangChain / LangGraph
- OpenAI API
- Vector DB (Pinecone vagy Chroma)