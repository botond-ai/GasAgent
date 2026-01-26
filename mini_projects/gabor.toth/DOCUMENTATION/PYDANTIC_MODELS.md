# 🔧 Pydantic Models - LangGraph Workflow

## Overview

A munkafolyamat Pydantic modelleket használ az input/output validációhoz és serializálásához. A `WorkflowState` TypedDict marad (LangGraph requirement), de az agent interface Pydantic modelleket használ.

## ✨ Pydantic Models

### 1. SearchStrategy (Enum)

Keresési stratégia típusok:

```python
class SearchStrategy(str, Enum):
    CATEGORY_BASED = "category_based"              # Kategória alapú keresés
    FALLBACK_ALL_CATEGORIES = "fallback_all_categories"  # Fallback az összes kategóriára
    HYBRID_SEARCH = "hybrid_search"                # Hibrid keresés
```

### 2. CitationSource

Forrás információ strukturált formátumban:

```python
class CitationSource(BaseModel):
    """Citation source information."""
    index: int                  # Idézet indexe a válaszban
    source: str                 # Forrás dokumentum vagy referencia
    distance: float            # Hasonlósági távolság (0=tökéletes, 1=legrosszabb)
    preview: str               # Az azonos szöveg előnézete
```

**Validáció**:
- `index`: Pozitív egész szám
- `source`: Nem üres string
- `distance`: 0.0 és 1.0 között
- `preview`: Nem üres string

**Példa**:
```python
citation = CitationSource(
    index=1,
    source="dokumentum.md",
    distance=0.95,
    preview="Az AI egy nagy intelligencia..."
)
```

### 3. SearchResult

Keresési operáció eredménye:

```python
class SearchResult(BaseModel):
    """Result of a search operation."""
    chunks: List[RetrievedChunk]                # Lekérdezett darabok
    strategy_used: SearchStrategy               # Használt stratégia
    search_time: float = Field(default=0.0)    # Keresés végrehajtási ideje (másodperc)
    error: Optional[str] = Field(default=None) # Hibaüzenet, ha a keresés sikertelen volt
```

**Validáció**:
- `chunks`: RetrievedChunk lista
- `strategy_used`: SearchStrategy enum
- `search_time`: Nem negatív float
- `error`: Opcionális string

**Példa**:
```python
result = SearchResult(
    chunks=[chunk1, chunk2, chunk3],
    strategy_used=SearchStrategy.CATEGORY_BASED,
    search_time=0.45,
    error=None
)
```

### 4. WorkflowInput

Munkafolyamat bemenetei:

```python
class WorkflowInput(BaseModel):
    """Input for the workflow."""
    user_id: str                    # Felhasználó ID
    question: str                   # Kérdés
    available_categories: List[str] # Elérhető kategóriák (opcionális)
```

**Validáció**:
- `user_id`: Min. 1 karakter
- `question`: Min. 5 karakter
- `available_categories`: String lista (alapértelmezés: üres lista)

**Példa**:
```python
input_data = WorkflowInput(
    user_id="user123",
    question="Mi az LangGraph?",
    available_categories=["docs", "tutorials"]
)
```

### 5. WorkflowOutput

Munkafolyamat kimenete:

```python
class WorkflowOutput(BaseModel):
    """Output of the workflow."""
    final_answer: str                           # Generált válasz
    answer_with_citations: str                  # Válasz inline idézetekkel
    citation_sources: List[CitationSource]      # Idézet metaadatok
    workflow_steps: List[str]                   # Munkafolyamat lépések
    error_messages: List[str]                   # Hibaüzenetek
    routed_category: Optional[str]              # Irányított kategória
    search_strategy: Optional[str]              # Keresési stratégia
    fallback_triggered: bool                    # Fallback keresés triggerelve-e
```

**Validáció**:
- `final_answer`: Nem üres string
- `answer_with_citations`: Nem üres string
- `citation_sources`: CitationSource lista
- `workflow_steps`: String lista
- `error_messages`: String lista
- `routed_category`: Opcionális string
- `search_strategy`: Opcionális string
- `fallback_triggered`: Boolean

**Példa**:
```python
output = WorkflowOutput(
    final_answer="LangGraph egy orchestration library...",
    answer_with_citations="LangGraph egy orchestration library[1]...",
    citation_sources=[
        CitationSource(
            index=1,
            source="docs.md",
            distance=0.98,
            preview="LangGraph egy orchestration library..."
        )
    ],
    workflow_steps=["validate_input", "category_routing", "embed_question", ...],
    error_messages=[],
    routed_category="docs",
    search_strategy="category_based",
    fallback_triggered=False
)
```

## 🔄 TypedDict vs Pydantic

### WorkflowState (TypedDict - LangGraph requirement)
- **Miért TypedDict?** LangGraph StateGraph TypedDict-et igényel
- **Milyen célra?** Belső state management a workflow lépések között
- **Serialization?** Nem szükséges, belső használat

### Input/Output Models (Pydantic)
- **Miért Pydantic?** Validáció, serializáció, API dokumentáció
- **Milyen célra?** Agent interfész, API kommunikáció
- **Serialization?** Támogatott JSON-hoz, OpenAPI schémahoz

## 💡 Előnyök

✅ **Input Validáció**
- Automatikus típus-ellenőrzés
- Min/max constraints (pl. string hossz)
- Enum validáció

✅ **Output Serializáció**
- JSON serializálás automatikus
- Swagger/OpenAPI schema generálás
- Type-safe API responses

✅ **IDE Support**
- Jobb autocomplete
- Type hints
- Better error messages

✅ **API Dokumentáció**
- FastAPI automatikusan dokumentálja
- JSON schema generálás
- Swagger UI

## 🚀 Használat az API-ban

### FastAPI Endpoint

```python
from fastapi import FastAPI
from backend.services import AdvancedRAGAgent
from backend.services.langgraph_workflow import WorkflowInput, WorkflowOutput

app = FastAPI()

@app.post("/api/answer", response_model=WorkflowOutput)
async def answer_question(input_data: WorkflowInput) -> WorkflowOutput:
    """Answer a question using the advanced RAG workflow."""
    agent = AdvancedRAGAgent(compiled_graph)
    
    output = await agent.answer_question(
        user_id=input_data.user_id,
        question=input_data.question,
        available_categories=input_data.available_categories
    )
    
    # output már WorkflowOutput (Pydantic model)
    return output  # Automatikusan JSON-ná alakul
```

### Generált OpenAPI Schema

```json
{
  "WorkflowInput": {
    "type": "object",
    "required": ["user_id", "question"],
    "properties": {
      "user_id": {
        "type": "string",
        "minLength": 1
      },
      "question": {
        "type": "string",
        "minLength": 5
      },
      "available_categories": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  },
  "WorkflowOutput": {
    "type": "object",
    "required": ["final_answer", "answer_with_citations"],
    "properties": {
      "final_answer": {"type": "string"},
      "answer_with_citations": {"type": "string"},
      "citation_sources": {
        "type": "array",
        "items": {"$ref": "#/components/schemas/CitationSource"}
      }
    }
  },
  "CitationSource": {
    "type": "object",
    "required": ["index", "source", "distance", "preview"],
    "properties": {
      "index": {"type": "integer", "minimum": 0},
      "source": {"type": "string"},
      "distance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
      "preview": {"type": "string"}
    }
  }
}
```

## 🔍 Validation Exempel

### Sikeres validáció

```python
# ✅ Valid
input_data = WorkflowInput(
    user_id="user123",
    question="What is LangGraph?",
    available_categories=["docs", "api"]
)
```

### Érvénytelen input

```python
# ❌ Túl rövid question
try:
    input_data = WorkflowInput(
        user_id="user123",
        question="Hi",  # Min. 5 karakter!
        available_categories=[]
    )
except ValueError as e:
    print(f"Validációs hiba: {e}")

# ❌ Hiányzó user_id
try:
    input_data = WorkflowInput(
        question="What is LangGraph?",
        available_categories=[]
    )
except ValueError as e:
    print(f"Validációs hiba: {e}")

# ❌ Érvénytelen distance a CitationSource-ban
try:
    citation = CitationSource(
        index=1,
        source="docs.md",
        distance=1.5,  # Max 1.0!
        preview="..."
    )
except ValueError as e:
    print(f"Validációs hiba: {e}")
```

## 📚 Integrációs Példák

### Python kliens

```python
from backend.services import create_advanced_rag_workflow, AdvancedRAGAgent
from backend.services.langgraph_workflow import WorkflowInput

# Workflow létrehozása
workflow = create_advanced_rag_workflow(
    category_router, embedding_service, 
    vector_store, rag_answerer
)
agent = AdvancedRAGAgent(workflow)

# Input Pydantic modellel
input_data = WorkflowInput(
    user_id="user123",
    question="What is LangGraph?",
    available_categories=["docs", "tutorials"]
)

# Output Pydantic modellként
output = await agent.answer_question(
    user_id=input_data.user_id,
    question=input_data.question,
    available_categories=input_data.available_categories
)

# Type-safe hozzáférés
print(output.final_answer)           # str
print(output.citation_sources)       # List[CitationSource]
print(output.workflow_steps)         # List[str]

# JSON serializálás
import json
json_output = output.model_dump_json(indent=2)
```

### FastAPI integrációs kód

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from backend.services import create_advanced_rag_workflow, AdvancedRAGAgent
from backend.services.langgraph_workflow import WorkflowInput, WorkflowOutput

app = FastAPI(
    title="Advanced RAG API",
    description="RAG API with Pydantic models"
)

# Global agent initialization
agent = None

@app.on_event("startup")
async def startup():
    global agent
    from infrastructure.repositories import (
        CategoryRouter, EmbeddingService, 
        VectorStore, RAGAnswerer
    )
    
    category_router = CategoryRouter()
    embedding_service = EmbeddingService()
    vector_store = VectorStore()
    rag_answerer = RAGAnswerer()
    
    workflow = create_advanced_rag_workflow(
        category_router, embedding_service,
        vector_store, rag_answerer
    )
    agent = AdvancedRAGAgent(workflow)

@app.post("/api/answer", response_model=WorkflowOutput)
async def answer_question(input_data: WorkflowInput) -> WorkflowOutput:
    """
    Answer a question using the advanced RAG workflow.
    
    Pydantic models handle:
    - Input validation
    - Output serialization
    - OpenAPI documentation
    """
    output = await agent.answer_question(
        user_id=input_data.user_id,
        question=input_data.question,
        available_categories=input_data.available_categories
    )
    return output
```

## 🔒 Error Handling

### Validációs hibák kezelése

```python
from pydantic import ValidationError

try:
    input_data = WorkflowInput(
        user_id="",  # Too short!
        question="What is LangGraph?",
    )
except ValidationError as e:
    print(e.json())  # Detailed error information
    # Output:
    # [
    #   {
    #     "loc": ["user_id"],
    #     "msg": "ensure this value has at least 1 character",
    #     "type": "value_error.string.min_length"
    #   }
    # ]
```

## 📖 Hivatkozások

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pydantic v2 Validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [FastAPI & Pydantic](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)

---

**Status**: ✅ Pydantic modellek integralva
**Files Updated**: langgraph_workflow.py
**Validáció**: Teljes
**API Documentation**: OpenAPI/Swagger ready
