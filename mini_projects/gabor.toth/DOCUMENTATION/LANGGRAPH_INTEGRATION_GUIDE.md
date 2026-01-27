# LangGraph Integrációs Útmutató - Lépésről Lépésre

## 1. Függőségek Frissítése

A `requirements.txt` már tartalmazza a `langgraph` és `langchain` könyvtárakat. Semmit sem kell módosítani.

## 2. Workflow Inicializálása a main.py-ben

Módosítsd a `main.py` fájl lifespan függvényt, hogy az új LangGraph workflowot inicializálja:

```python
# Hozzáadás az importoknál
from services.langgraph_workflow import create_advanced_rag_workflow, AdvancedRAGAgent

# A lifespan függvényben, az eredeti RAGAgent inicializálása után:

global langgraph_workflow, advanced_rag_agent

# ... meglévő kód ...

# Új: LangGraph workflow inicializálása
langgraph_workflow = create_advanced_rag_workflow(
    category_router=category_router,
    embedding_service=embedding_service,
    vector_store=vector_store,
    rag_answerer=rag_answerer
)

advanced_rag_agent = AdvancedRAGAgent(langgraph_workflow)

# Opcionális: az eredeti RAGAgent megtartása backward compatibilityhez
chat_service = ChatService(
    rag_agent=advanced_rag_agent,  # Az új agent
    profile_repo=profile_repo,
    session_repo=session_repo,
    upload_repo=upload_repo,
    activity_callback=activity_callback,
)
```

## 3. Workflow Vizualizálása

A LangGraph workflow vizualizálható a mermaid diagrammal:

```python
# Workflow vizualizálása (opcionális, development-hez)
from IPython.display import Image, display

# ASCII art output
print(langgraph_workflow.get_graph().draw_ascii())

# PNG output (ha graphviz telepítve van)
try:
    png_bytes = langgraph_workflow.get_graph().draw_mermaid_png()
    with open("workflow_visualization.png", "wb") as f:
        f.write(png_bytes)
except Exception as e:
    print(f"Visualization error: {e}")
```

## 4. Activity Callback Integrálása

Az activity callback már támogatott az új workflowban. Az összes node loggol:

```python
# A workflow automatikusan loggol az activity_callback-en keresztül:
# - "validate_input" node: nincs log
# - "category_routing" node: kategória kiválasztása
# - "embed_question" node: beágyazás progress
# - "search_category" node: keresés progress
# - "evaluate_search" node: minőség értékelés
# - "fallback_search" node: fallback aktiválódás
# - "dedup_chunks" node: nincs log
# - "generate_answer" node: válasz generálás progress
# - "format_response" node: nincs log
```

## 5. Frontend Kompatibilitás

Az `/api/chat` endpoint a ChatService-ből jön, amely az AdvancedRAGAgent WorkflowOutput-ját egy standardizált JSON formátumba transzformálja:

```javascript
// Frontend API hívás
const result = await fetch('/api/chat', {
    method: 'POST',
    body: new FormData({
        user_id: 'user123',
        session_id: 'session456',
        message: 'My question'
    })
}).then(r => r.json());

// API Response mezői
console.log(result.final_answer);           // String: LLM-generált válasz
console.log(result.fallback_search);        // Boolean: fallback keresés használva?
console.log(result.memory_snapshot);        // Object:
                                            //   - routed_category: String
                                            //   - available_categories: Array
console.log(result.rag_debug);              // Object:
                                            //   - retrieved: Array [
                                            //       {chunk_id, content, source_file, 
                                            //        section_title, distance, snippet}
                                            //     ]
console.log(result.debug_steps);            // Array: [
                                            //   {node, status, duration_ms}
                                            // ]
console.log(result.api_info);               // Object:
                                            //   - endpoint: '/api/chat'
                                            //   - method: 'POST'
                                            //   - status_code: 200
                                            //   - response_time_ms: number

// Lekért dokumentumok iterálása
result.rag_debug.retrieved.forEach(chunk => {
    console.log(chunk.content);             // Teljes szöveg a dokumentumból
    console.log(chunk.source_file);         // Forrás fájl neve
    console.log(chunk.section_title);       // Fejezet/szekció cím
    console.log(chunk.distance);            // Hasonlósági score (0.0-1.0)
    console.log(chunk.chunk_id);            // Chunk azonosító
});
```

## 6. Error Handling

Az új workflow jobb error handling-gel rendelkezik. Az error_messages mező naplózza az előforduló hibákat:

```python
# WorkflowOutput error handling
result = await agent.answer_question(...)

if result.error_messages:
    for error in result.error_messages:
        logger.error(f"Workflow error: {error}")

# ChatService API error response
# Ha a ChatService hiba lépne fel, a /api/chat még válaszol, de error mezővel:
try:
    response = await chat_service.process_message(...)
except Exception as e:
    response = {
        "final_answer": f"Hiba történt: {str(e)}",
        "error": str(e),
        "api_info": {
            "status_code": 500,
            "endpoint": "/api/chat"
        }
    }
```

## 7. Testing az Új Workflowval

```python
import pytest
from services.langgraph_workflow import create_advanced_rag_workflow, AdvancedRAGAgent

@pytest.fixture
async def advanced_agent(
    category_router, embedding_service, vector_store, rag_answerer
):
    workflow = create_advanced_rag_workflow(
        category_router=category_router,
        embedding_service=embedding_service,
        vector_store=vector_store,
        rag_answerer=rag_answerer
    )
    return AdvancedRAGAgent(workflow)

@pytest.mark.asyncio
async def test_end_to_end_workflow(advanced_agent):
    """Test complete workflow."""
    result = await advanced_agent.answer_question(
        user_id="test_user",
        question="Test question?",
        available_categories=["test_cat"],
        activity_callback=None
    )
    
    assert result['final_answer'] is not None
    assert result['workflow_steps'] is not None
    assert len(result['workflow_steps']) > 0
    assert 'answer_generated' in result['workflow_steps']
    assert 'response_formatted' in result['workflow_steps']
```

## 8. Monitoring és Observability

```python
# Workflow metrics export
result = await agent.answer_question(...)

# Workflow steps tracking
print(f"Steps executed: {result['workflow_steps']}")
# Output: ['input_validated', 'category_routed', 'question_embedded', ...]

# Search strategy tracking
print(f"Search strategy: {result['search_strategy']}")
# Output: 'CATEGORY_BASED' vagy 'FALLBACK_ALL_CATEGORIES'

# Fallback trigger tracking
print(f"Fallback triggered: {result['fallback_triggered']}")
```

## 9. Performance Analysis

```python
import time

# Workflow futási idő mérlése
start_time = time.time()
result = await agent.answer_question(
    user_id="user123",
    question="Complex question?",
    available_categories=["docs", "tutorials", "faq"]
)
elapsed_time = time.time() - start_time

print(f"Workflow execution time: {elapsed_time:.2f}s")
print(f"Steps: {len(result['workflow_steps'])}")
print(f"Fallback used: {result['fallback_triggered']}")
```

## 10. Migráció a ChatService-ben

Jelenleg a ChatService polymorphic módon működik:

```python
# Régi interface
rag_agent: RAGAgent

# Új interface (drop-in replacement)
rag_agent: AdvancedRAGAgent

# Mindkettő implementálja az answer_question async metódust:
await rag_agent.answer_question(user_id, question, available_categories, callback)
```

## 11. Backward Compatibility

Az eredeti `RAGAgent` még mindig elérhető:

```python
from services.rag_agent import create_rag_agent, RAGAgent

# Régi kód továbbra működik
legacy_agent = RAGAgent(
    compiled_graph=create_rag_agent(
        category_router,
        embedding_service,
        vector_store,
        rag_answerer
    )
)
```

A `ChatService` automatikusan működik mindkét agent-tel.

## 12. Debugging a Workflowban

```python
# Workflow state inspection
from langgraph.graph import StateGraph

# A compiled graph megvizsgálható:
print(langgraph_workflow.get_graph().nodes)
# Output: dict_keys(['validate_input', 'category_routing', ...])

print(langgraph_workflow.get_graph().edges)
# Output: list of (source, dest) tuples

# State transitions nyomkövetése
class DebugCallback:
    async def log_activity(self, message, activity_type="info", metadata=None):
        print(f"[{activity_type}] {message} - {metadata}")

result = await agent.answer_question(
    ...,
    activity_callback=DebugCallback()
)
```

## 13. Konfiguráció Opciók

Az új workflow konfigurálható:

```python
# search_category_node-ban
top_k = 5  # Top-k dokumentum lekérése

# evaluate_search_node-ban
min_similarity_threshold = 0.3  # Fallback trigger küszöbérték

# fallback_search_node-ban
fallback_top_k = 3  # Top-k dokumentum fallback keresésben

# Ezek hardkódoltak, de könnyűen parameterize-hatók
```

## 14. Produkciós Deployment

```bash
# Docker build
docker build -t rag-agent:langgraph .

# Docker run
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY \
           -p 8000:8000 \
           rag-agent:langgraph

# Health check
curl http://localhost:8000/health
```

## 15. Összefoglalás

| Szempont | Régi RAGAgent | Új AdvancedRAGAgent |
|----------|---------------|-------------------|
| Szerkezet | Szekvenciális | Gráf-alapú |
| Csomópontok | 3 | 9 |
| Fallback | Egyszerű | Intelligens |
| State tracking | Alapvető | Comprehensive |
| Activity logging | Nincs | Teljes |
| Citation handling | Nincs | Strukturált |
| Extensibility | Mérsékelt | Magas |
| Testing | Nehéz | Könnyű |
| Performance metrics | Nincs | Teljes |

## Kapcsolódó Fájlok

- `backend/services/langgraph_workflow.py` - Új implementáció
- `LANGGRAPH_IMPLEMENTATION.md` - Technikai dokumentáció
- `backend/main.py` - Integration point

## Support

Ha kérdéseid vannak az integráció során, tekintsd meg:

1. `LANGGRAPH_IMPLEMENTATION.md` - Technikai részletek
2. `langgraph_workflow.py` - Forráskód és docstringek
3. Frontend komponensek - Activity logging vizualizáció
