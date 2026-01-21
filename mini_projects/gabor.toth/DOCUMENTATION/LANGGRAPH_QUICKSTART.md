# LangGraph Workflow - Gyors Kezdeti Útmutató

## ⚡ 5 Perc alatt a Workflow-nal

### 1. Telepítés (már kész)

```bash
# requirements.txt már tartalmazza:
pip install langgraph>=0.0.0
pip install langchain>=0.1.0
pip install langchain-core>=0.1.0
```

### 2. A Workflow Importálása

```python
from services.langgraph_workflow import (
    create_advanced_rag_workflow,
    AdvancedRAGAgent
)
```

### 3. Workflow Inicializálása

```python
# Az összes szükséges komponens biztosítása
workflow = create_advanced_rag_workflow(
    category_router=category_router,
    embedding_service=embedding_service,
    vector_store=vector_store,
    rag_answerer=rag_answerer
)

agent = AdvancedRAGAgent(workflow)
```

### 4. Kérdés Feldolgozása

```python
result = await agent.answer_question(
    user_id="user123",
    question="Hogyan kell használni az API-t?",
    available_categories=["docs", "tutorials", "faq"],
    activity_callback=activity_callback  # optional
)
```

### 5. Eredmény Használata

```python
# Az API válaszból az alábbi mezőket kapod:
print(f"Válasz: {result['final_answer']}")
print(f"Kategória: {result['memory_snapshot']['routed_category']}")
print(f"Lekért chunkok: {result['rag_debug']['retrieved']}")
print(f"API válasz idő: {result['api_info']['response_time_ms']}ms")
print(f"Workflow lépések: {result['debug_steps']}")
```

## 📊 Az Új Workflow Előnyei

| Szempont | Régi | Új |
|----------|------|-----|
| **Csomópontok** | 3 | 9 |
| **Fallback** | ❌ Nincs | ✅ Intelligens |
| **Monitoring** | ❌ Nincs | ✅ Teljes |
| **Citations** | ❌ Nyers | ✅ Strukturált |
| **Error handling** | 🟡 Alapvető | ✅ Komprehenzív |
| **Testing** | 🟡 Nehéz | ✅ Könnyű |
| **Bővíthetőség** | 🟡 Mérsékelt | ✅ Magas |

## 🎯 A 9 Csomópont Röviden

```
1. ✅ validate_input        - Input ellenőrzés
2. 🎯 category_routing      - Kategória kiválasztás
3. 🔢 embed_question        - Vektor beágyazás
4. 📚 search_category       - Keresés az kategóriában
5. 🔎 evaluate_search       - Minőség értékelés
6. 🔄 fallback_search       - Fallback keresés
7. 🧹 dedup_chunks          - Duplikálódás eltávolítása
8. 🤖 generate_answer       - Válasz generálás
9. ✨ format_response       - Citációk formázása
```

## 🔍 Workflow State Felépítése

Az **AdvancedRAGAgent** egy **WorkflowOutput** objektumot ad vissza, mely tartalmazza:

```python
{
    # Alapvető válasz
    "final_answer": str,                 # LLM-generált válasz
    
    # Kategória routing
    "routed_category": str,              # Felismert kategória
    
    # Retrieval információ
    "context_chunks": List[RetrievedChunk],  # Lekért dokumentum részletek
    "search_strategy": str,              # CATEGORY_BASED vagy FALLBACK
    "fallback_triggered": bool,          # Fallback keresés aktiválva?
    
    # Generálási információ
    "answer_with_citations": str,        # Válasz citációkkal
    "citation_sources": List[Dict],      # Citáció forrás adatok
    
    # Debug információ
    "workflow_steps": List[str],         # Végrehajtott lépések
    "error_messages": List[str],         # Hibák (ha vannak)
    "workflow_logs": List[Dict],         # Részletes végrehajtás logok
}
```

### Az API EndPoint

Az `/api/chat` endpoint az **AdvancedRAGAgent** visszatérési értékét transzformálja egy standardizált JSON formátumba:

```json
{
    "final_answer": "Kérdés válasza...",
    "tools_used": [],
    "fallback_search": false,
    "memory_snapshot": {
        "routed_category": "kategória_nev",
        "available_categories": ["cat1", "cat2", "cat3"]
    },
    "rag_debug": {
        "retrieved": [
            {
                "chunk_id": 1,
                "content": "Teljes szöveg a dokumentumból",
                "source_file": "Document.md",
                "section_title": "Fejezet cím",
                "distance": 0.45,
                "snippet": "Rövid előnézet...",
                "metadata": {}
            }
        ]
    },
    "debug_steps": [
        {
            "node": "validate_input",
            "status": "completed",
            "duration_ms": 12.34
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

## 🚀 Integrálása a ChatService-ben

A **ChatService** az **AdvancedRAGAgent** válaszát a `/api/chat` JSON formátumba transzformálja:

```python
# Integrálás a ChatService-ben (backend/main.py-ben)
rag_agent = AdvancedRAGAgent(compiled_graph, tool_registry)
chat_service = ChatService(rag_agent, profile_repo, session_repo, upload_repo, activity_callback)

# A ChatService automatikusan:
# 1. Felhasználó profilt betöltésével vagy létrehozásával
# 2. Kategória routing
# 3. RAG agent futtatásával
# 4. WorkflowOutput -> API JSON formátumba transzformálásával
response = await chat_service.process_message(user_id, session_id, message)
# response = {
#     "final_answer": "...",
#     "rag_debug": {...},
#     "api_info": {...}
# }
```

## 📝 Activity Logging

A workflow automatikusan loggol az activity callback-en keresztül:

```python
from domain.interfaces import ActivityCallback

class MyActivityCallback(ActivityCallback):
    async def log_activity(self, message: str, activity_type: str = "info", metadata: dict = None):
        print(f"[{activity_type}] {message}")

# Workflow loggolása
result = await agent.answer_question(
    ...,
    activity_callback=MyActivityCallback()
)
```

## 🧪 Tesztelés

```python
import pytest

@pytest.mark.asyncio
async def test_workflow():
    # Kérdés feldolgozása
    result = await agent.answer_question(
        user_id="test_user",
        question="Test question?",
        available_categories=["test_cat"],
        activity_callback=None
    )
    
    # Ellenőrzések
    assert result.final_answer is not None
    assert "answer_generated" in result.workflow_steps
    assert result.search_strategy is not None
    assert len(result.context_chunks) >= 0  # Lehet 0 ha nincs találat
    
    # API válasz tesztelése
    api_response = await chat_service.process_message("user_id", "session_id", "Test?")
    assert "final_answer" in api_response
    assert "rag_debug" in api_response
    assert "api_info" in api_response
    assert api_response["api_info"]["status_code"] == 200
```

## 🔧 Debuggolás

```python
# WorkflowOutput debuggolása
result = await agent.answer_question(
    user_id="user123",
    question="Test question?",
    available_categories=["test_cat"]
)

# Workflow lépések nyomkövetése
print("Workflow lépések:")
for step in result.workflow_steps:
    print(f"  ✓ {step}")

# Retrieved chunks vizsgálata
print(f"\nLekért chunks: {len(result.context_chunks)}")
for chunk in result.context_chunks:
    print(f"  - {chunk.chunk_id}: {chunk.section_title} (relevancia: {chunk.distance:.2f})")

# Keresési stratégia és fallback
print(f"\nKeresési stratégia: {result.search_strategy}")
print(f"Fallback triggerelt: {result.fallback_triggered}")

# Hibák ellenőrzése
if result.error_messages:
    print(f"Hibák: {', '.join(result.error_messages)}")

# API válasz debuggolása
api_response = await chat_service.process_message("user_id", "session_id", "Test?")
print(f"\nAPI válasz ideje: {api_response['api_info']['response_time_ms']}ms")
print(f"Kategória: {api_response['memory_snapshot']['routed_category']}")
```

## 📚 Dokumentáció

| Fájl | Tartalom |
|------|----------|
| `langgraph_workflow.py` | Implementáció |
| `LANGGRAPH_IMPLEMENTATION.md` | Technikai részletek |
| `LANGGRAPH_INTEGRATION_GUIDE.md` | Integrálási útmutató |
| `LANGGRAPH_WORKFLOW_DIAGRAMS.md` | Vizuális diagramok |
| `test_langgraph_workflow.py` | Unit tesztek |

## ❓ Gyakori Kérdések

**K: Működik az új workflow az old code-dal?**
A: Igen! A ChatService polymorphic módon támogatja mindkét agentot.

**K: Mit csinál a fallback search?**
A: Ha az első keresés nem adott elég jó eredményt, keresész az összes kategóriában.

**K: Mi a workflow_steps?**
A: Nyomkövetés, hogy mely csomópontok futottak: `["input_validated", "category_routed", ...]`

**K: Hogyan loggolok az activity callback-ből?**
A: Lásd az Activity Logging szekciót.

**K: Lehet-e testreszabni a fallback kritériumokat?**
A: Igen, szerkessze az `evaluate_search_node` függvényt.

## 🎓 Tanulási Útvonal

1. Olvass el `LANGGRAPH_IMPLEMENTATION.md` - technikai áttekintés
2. Vizsgáld meg `langgraph_workflow.py` - forráskód
3. Nézd meg `LANGGRAPH_WORKFLOW_DIAGRAMS.md` - vizuális reprezentáció
4. Futtasd a testeket: `pytest backend/tests/test_langgraph_workflow.py`
5. Integrálj a main.py-ba az `LANGGRAPH_INTEGRATION_GUIDE.md` szerint

## 🆘 Support

Technikai kérdésekre, lásd az `LANGGRAPH_IMPLEMENTATION.md` részleteket,
valamint a forráskód docstringjeit.

---

**Kész az indulásra? Kezdj az 5 perces útmutatóval fent!** 🚀
