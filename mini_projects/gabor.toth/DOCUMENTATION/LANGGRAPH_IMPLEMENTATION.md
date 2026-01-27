# LangGraph Workflow Implementáció - Gráf Alapú Agent Orkestrálás

## Áttekintés

Az új **LangGraph workflow** egy fejlett, gráf-alapú megközelítést implementál, amely a szekvenciális vezénylést egy rugalmas csomópont-rendszerrel helyettesíti. Minden API-hívás és üzleti logikai lépés egy meghatározott csomóponttá válik a munkafolyamat-gráfban.

## Architektúra

### Gráf Topológia

```
┌─────────────────┐
│ validate_input  │ (Input validáció)
└────────┬────────┘
         │
┌────────▼──────────────┐
│ category_routing      │ (LLM kategória routing)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ embed_question        │ (Kérdés beágyazása)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ search_category       │ (Keresés a routed kategóriában)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ evaluate_search       │ (Keresési minőség értékelése)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ fallback_search       │ (Fallback - összes kategória)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ dedup_chunks          │ (Duplikálódás eltávolítása)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ generate_answer       │ (Válasz generálás)
└────────┬──────────────┘
         │
┌────────▼──────────────┐
│ format_response       │ (Válasz formázás citációkkal)
└────────┬──────────────┘
         │
      [END]
```

## Csomópontok Leírása

### 1. `validate_input`
**Cél**: Input adatok validálása
- Ellenőrzi, hogy a kérdés nem üres
- Ellenőrzi, hogy vannak elérhető kategóriák
- Inicializálja a workflow_steps listát

### 2. `category_routing`
**Cél**: Kérdés irányítása megfelelő kategóriához
- LLM-alapú kategória döntés
- Visszaad kategóriát, magabiztosságot és indoklást
- Activity callback-en keresztül loggol a frontend felé

### 3. `embed_question`
**Cél**: A kérdés átalakítása vektorba
- OpenAI embedding API használata
- Az embedding-et tárja az `question_embedding` mezőben
- Critical a vektor-hasonlósági kereséshez

### 4. `search_category`
**Cél**: Dokumentumok keresése a routed kategóriában
- ChromaDB query az embedded question-vel
- Top-5 dokumentum lekérése
- Keresési stratégia: `CATEGORY_BASED`

### 5. `evaluate_search`
**Cél**: A keresési eredmények minőségének értékelése
- Ellenőrzi, hogy van-e elegendő dokumentum
- Vizsgálja az átlagos hasonlósági pontszámot
- Fallback trigger: nincs dokumentum VAGY túl alacsony hasonlóság

### 6. `fallback_search`
**Cél**: Fallback keresés az összes kategóriában
- Csak akkor fut, ha `fallback_triggered` true
- Keresés az összes többi kategóriában
- Top-3 dokumentum kategóriánként
- Keresési stratégia: `FALLBACK_ALL_CATEGORIES`

### 7. `dedup_chunks`
**Cél**: Duplikálódások eltávolítása a dokumentumok közül
- Hash alapú deduplicálás
- Az első előfordulást tartja meg
- Megőrzi a sorrendet

### 8. `generate_answer`
**Cél**: OpenAI LLM-mel válasz generálása
- RAGAnswerer interface használata
- Dokumentumok kontextussal paraméterezve
- Citációk integrálva a válaszba

### 9. `format_response`
**Cél**: Válasz formázása citációkkal
- Citation sources lista felépítése
- Előnézet + metadatok csatolása
- Frontend-ready formátum

## Workflow State TypedDict

```python
class WorkflowState(TypedDict):
    # Input
    user_id: str                          # Felhasználó azonosító
    question: str                         # Az eredeti kérdés
    available_categories: List[str]       # Elérhető kategóriák
    activity_callback: Optional[...]      # Logging callback
    
    # Category routing
    routed_category: Optional[str]        # Kiválasztott kategória
    category_confidence: float            # Magabiztosság 0-1
    category_reason: str                  # Indoklás
    category_routing_attempts: int        # Újrapróbálkozások száma
    
    # Retrieval
    context_chunks: List[RetrievedChunk]  # Lekért dokumentumok
    search_strategy: SearchStrategy       # Alkalmazott keresési stratégia
    search_results: List[SearchResult]    # Keresési eredmények
    fallback_triggered: bool              # Fallback aktiválva?
    retrieval_status: str                 # Keresés status
    
    # Generation
    final_answer: str                     # Végső válasz
    answer_with_citations: str            # Válasz citációkkal
    citation_sources: List[Dict]          # Citáció források
    
    # Metadata
    workflow_steps: List[str]             # Végrehajtott lépések
    error_messages: List[str]             # Hibák
    performance_metrics: Dict[str, float] # Teljesítmény adatok
```

## API Integrálás

### API Hívások Leképezése Csomópontokra

| API | Csomópont | Cél |
|-----|-----------|-----|
| `category_router.decide_category()` | category_routing | Kategória kiválasztása |
| `embedding_service.embed_text()` | embed_question + fallback_search | Szöveg vektorizálása |
| `vector_store.query()` | search_category + fallback_search | Vektor-hasonlóság keresés |
| `rag_answerer.generate_answer()` | generate_answer | LLM válasz generálás |

### Asynchronous vs Synchronous Nodes

- **Async logika**: Minden API-hívás async (OpenAI, Chroma, stb.)
- **Node wrapper**: Csomópontok sync kell legyenek LangGraph-hez
- **Megoldás**: `asyncio.run()` wrapper minden async operációhoz

```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(
        async_function(...)
    )
finally:
    loop.close()
```

## Keresési Stratégiák

### 1. CATEGORY_BASED
- **Aktiválódás**: Az első keresés a routed kategóriában
- **Eredmények**: 5 top dokumentum
- **Fallback**: Ha túl kevés/gyenge dokumentum

### 2. FALLBACK_ALL_CATEGORIES
- **Aktiválódás**: Ha kategóriás keresés gyenge
- **Eredmények**: 3 top dokumentum / kategória
- **Indok**: Robusztusság és comprehensive keresés

### 3. HYBRID_SEARCH (kiterjesztés lehetőség)
- Kombinálja: kategóriás + kulcsszó keresés
- BM25 full-text search integrálható

## Usage Példa

### WorkflowOutput (Backend)

```python
from services.langgraph_workflow import create_advanced_rag_workflow, AdvancedRAGAgent

# Workflow inicializálása
workflow = create_advanced_rag_workflow(
    category_router=category_router,
    embedding_service=embedding_service,
    vector_store=vector_store,
    rag_answerer=rag_answerer
)

agent = AdvancedRAGAgent(workflow)

# Kérdés feldolgozása - WorkflowOutput-t kapunk vissza
result = await agent.answer_question(
    user_id="user123",
    question="Hogyan kell használni az API-t?",
    available_categories=["docs", "tutorials", "faq"],
    activity_callback=activity_callback
)

# WorkflowOutput objektum mezői
print(f"Válasz: {result.final_answer}")
print(f"Kategória: {result.routed_category}")
print(f"Keresési stratégia: {result.search_strategy}")
print(f"Fallback triggerelt: {result.fallback_triggered}")
print(f"Workflow lépések: {result.workflow_steps}")
print(f"Lekért chunks: {len(result.context_chunks)}")
```

### API Response (Frontend)

A `/api/chat` endpoint az `WorkflowOutput`-ot a frontend számára optimalizált formátumba transzformálja:

```json
{
  "final_answer": "Az API-t az OpenAI SDK-val lehet...",
  "tools_used": [],
  "fallback_search": false,
  "memory_snapshot": {
    "routed_category": "docs",
    "available_categories": ["docs", "tutorials", "faq"]
  },
  "rag_debug": {
    "retrieved": [
      {
        "chunk_id": 1,
        "content": "Full text from document...",
        "source_file": "API_Guide.md",
        "section_title": "Getting Started",
        "distance": 0.42,
        "snippet": "The API guide explains...",
        "metadata": {}
      }
    ]
  },
  "debug_steps": [
    {
      "node": "validate_input",
      "status": "completed",
      "duration_ms": 1.23
    }
  ],
  "api_info": {
    "endpoint": "/api/chat",
    "method": "POST",
    "status_code": 200,
    "response_time_ms": 1234.56
  }
}
```

### Frontend Integráció

```typescript
// React komponens
const response = await chat_service.sendMessage(question);

// WorkflowOutput -> API JSON transzformálás automatikus (ChatService)
console.log(response.final_answer);
console.log(response.rag_debug.retrieved);
console.log(response.api_info.response_time_ms);
```

## Főbb Javítások az Eredeti Implementációhoz Képest

1. **Gráf-alapú Struktura**: Explicit csomópont-rendszer helyett szekvenciális kódnak
2. **Moduláris Csomópontok**: Minden csomópont önálló, testelhető
3. **Bővített State Management**: Comprehensive workflow state TypedDict
4. **Fallback Stratégia**: Intelligens fallback a keresési minőség alapján
5. **Activity Logging**: Cada csomópont loggol az activity callbacken keresztül
6. **Performance Metrics**: Teljesítmény adatok gyűjtése
7. **Citation Sources**: Strukturált citáció kezelés
8. **Error Handling**: Jobb hibakezelés és error reporting
9. **Extensibility**: Könnyen bővíthető új csomópontokkal
10. **State Traceability**: Workflow steps listával nyomkövethetőség

## Integrálása a ChatService-be

A `ChatService` az új AdvancedRAGAgent-et használja az eredeti RAGAgent helyett:

```python
# main.py-ban
from services.langgraph_workflow import create_advanced_rag_workflow, AdvancedRAGAgent

# Workflow inicializálása
langgraph_workflow = create_advanced_rag_workflow(...)
advanced_rag_agent = AdvancedRAGAgent(langgraph_workflow)

# ChatService inicializálása az új agenttel
chat_service = ChatService(
    rag_agent=advanced_rag_agent,  # Polymorphic - ugyanaz az interface
    ...
)
```

## Testing

### Unit Teszt Sablonok

```python
import pytest
from services.langgraph_workflow import AdvancedRAGAgent

@pytest.mark.asyncio
async def test_workflow_category_routing():
    """Test category routing node."""
    agent = AdvancedRAGAgent(compiled_graph)
    
    result = await agent.answer_question(
        user_id="test_user",
        question="How to use the API?",
        available_categories=["docs", "tutorials"],
        activity_callback=None
    )
    
    assert result.routed_category in ["docs", "tutorials"]
    assert "category_routed" in result.workflow_steps

@pytest.mark.asyncio
async def test_fallback_search_trigger():
    """Test fallback search triggering when initial results are poor."""
    agent = AdvancedRAGAgent(compiled_graph)
    
    result = await agent.answer_question(
        user_id="test_user",
        question="Obscure question that likely returns few results",
        available_categories=["docs"],
        activity_callback=None
    )
    
    # If no good results from first category, fallback should trigger
    if len(result.context_chunks) < 2:
        assert result.fallback_triggered == True

@pytest.mark.asyncio
async def test_api_response_format():
    """Test API response format (ChatService level)."""
    response = await chat_service.process_message(
        user_id="test_user",
        session_id="test_session",
        message="Test question?"
    )
    
    # Verify API response structure
    assert "final_answer" in response
    assert "rag_debug" in response
    assert "api_info" in response
    assert "memory_snapshot" in response
    assert response["api_info"]["status_code"] == 200
    assert response["api_info"]["response_time_ms"] > 0
```

### Integration Teszt

```python
@pytest.mark.asyncio
async def test_end_to_end_workflow():
    """End-to-end test from question to API response."""
    # Upload test documents
    upload_result = await upload_service.upload(
        user_id="test_user",
        file_stream=test_file,
        category="test_cat"
    )
    assert upload_result.success
    
    # Query the system
    response = await chat_service.process_message(
        user_id="test_user",
        session_id="test_session",
        message="Question about test document?"
    )
    
    # Verify response
    assert response["final_answer"]
    assert len(response["rag_debug"]["retrieved"]) > 0
    assert response["memory_snapshot"]["routed_category"] == "test_cat"
```

## Teljesítmény Optimalizálások

1. **Caching**: Embedding cache az gyakori kérdésekhez
2. **Batch Processing**: Több kérdés egyidejű feldolgozása
3. **Early Exit**: Ha kategória nem létezik, skip a keresést
4. **Connection Pooling**: ChromaDB connection reuse

## Jövőbeli Kiterjesztések

1. **Multi-hop Retrieval**: Több lépésben refining a keresést
2. **Question Decomposition**: Összetett kérdések kisebb lépésekre bontása
3. **Re-ranking**: BM25/ColBERT-alapú re-ranking
4. **Conversational Context**: Múlt üzenetek figyelembevétele
5. **Tool Integration**: Külső API-k meghívása (calculator, weather, stb.)
