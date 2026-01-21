# 🚀 Pydantic Models - Rövid Útmutató

## Miről van szó?

Az Agent most Pydantic modelleket használ az input/output-hoz. Ez azt jelenti:
- ✅ Automatikus validáció
- ✅ Jobb IDE support
- ✅ OpenAPI dokumentáció
- ✅ Type safety

## 5 Perc alatt

### 1. Modellek importálása

```python
from backend.services import (
    AdvancedRAGAgent,
    WorkflowInput,
    WorkflowOutput,
    CitationSource,
)
```

### 2. Input létrehozása

```python
# ✅ Érvényes input
input_data = WorkflowInput(
    user_id="user123",
    question="Mi az LangGraph?",
    available_categories=["docs", "api"]
)

# ❌ Hibás (túl rövid question)
try:
    bad_input = WorkflowInput(
        user_id="user123",
        question="Hi",  # Min 5 char!
    )
except ValidationError as e:
    print(f"Hiba: {e}")
```

### 3. Workflow futtatása

```python
agent = AdvancedRAGAgent(compiled_graph)

output = await agent.answer_question(
    user_id=input_data.user_id,
    question=input_data.question,
    available_categories=input_data.available_categories
)

# output már WorkflowOutput típus!
print(output.final_answer)           # IDE knows this is str
print(output.citation_sources)       # IDE knows this is List[CitationSource]
```

### 4. Output feldolgozása

```python
# Type-safe hozzáférés
for citation in output.citation_sources:
    print(f"{citation.index}. {citation.source} ({citation.distance:.2f})")

# JSON konverziós
json_string = output.model_dump_json(indent=2)

# Dict konverzió
output_dict = output.model_dump()
```

## Validációs Szabályok

### WorkflowInput
- `user_id`: legalább 1 karakter
- `question`: legalább 5 karakter
- `available_categories`: string lista (opcionális)

### CitationSource
- `index`: pozitív egész
- `source`: nem üres string
- `distance`: 0.0 és 1.0 között
- `preview`: nem üres string

### WorkflowOutput
- `final_answer`: nem üres string
- `answer_with_citations`: nem üres string
- `citation_sources`: CitationSource lista
- `workflow_steps`: string lista
- `error_messages`: string lista
- `routed_category`: opcionális string
- `search_strategy`: opcionális string
- `fallback_triggered`: boolean

## Gyakori Problémák

### 1. ValidationError: "ensure this value has at least 5 characters"
```python
# ❌ Hibás
input_data = WorkflowInput(user_id="user123", question="Hi")

# ✅ Helyes
input_data = WorkflowInput(user_id="user123", question="What is AI?")
```

### 2. Attribútum nem elérhető
```python
# ❌ Hibás (dict syntax)
answer = output["final_answer"]

# ✅ Helyes (Pydantic syntax)
answer = output.final_answer
```

### 3. JSON serializálás
```python
# ✅ Automatikus
json_str = output.model_dump_json()

# ✅ Dict-ből JSON
import json
data_dict = output.model_dump()
json_str = json.dumps(data_dict)
```

## FastAPI Integrációs Minta

```python
from fastapi import FastAPI
from backend.services import AdvancedRAGAgent, WorkflowInput, WorkflowOutput

app = FastAPI()

@app.post("/api/answer", response_model=WorkflowOutput)
async def answer_question(input_data: WorkflowInput) -> WorkflowOutput:
    """
    Answer a question.
    
    - **user_id**: User making the request
    - **question**: The question to answer (min 5 chars)
    - **available_categories**: Categories to search
    
    Returns structured answer with citations.
    """
    agent = AdvancedRAGAgent(compiled_graph)
    
    output = await agent.answer_question(
        user_id=input_data.user_id,
        question=input_data.question,
        available_categories=input_data.available_categories
    )
    
    return output  # Automatically JSON serialized
```

FastAPI automatikusan generál:
- ✅ OpenAPI schema
- ✅ Swagger UI dokumentáció
- ✅ Input validáció
- ✅ Output serializálás

## Tesztelés

```bash
# Összes Pydantic teszt
pytest backend/tests/test_langgraph_workflow.py::TestPydanticModels -v

# Egyedi teszt
pytest backend/tests/test_langgraph_workflow.py::TestPydanticModels::test_workflow_input_valid -v
```

## Teljes Dokumentáció

Részletesebb információ: **PYDANTIC_MODELS.md**

---

**Kész? Kezdj el fejleszteni!** 🚀
