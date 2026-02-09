# LLM Prompt Input/Output Strukturált Elemzés

## 📋 Jelenlegi Állapot

### Promptolási Helyek a Rendszerben

#### 1. **Intent Detection** (`agent.py:_intent_detection_node`)
**Input:**
- Prompt: String template simple classification taskhoz
- Message: `HumanMessage(content=prompt)`

**Output:**
- Raw text válasz: `response.content.strip().lower()`
- Domain validation: `DomainType(domain)` enum check

**Probléma:** ❌ Nincs strukturált output
**Javítandó:** 
```python
# Jelenlegi
response = await self.llm.ainvoke([HumanMessage(content=prompt)])
domain = response.content.strip().lower()

# Strukturált verzió (javaslat)
from pydantic import BaseModel

class IntentDetectionOutput(BaseModel):
    domain: DomainType
    confidence: float
    reasoning: str

structured_llm = self.llm.with_structured_output(IntentDetectionOutput)
result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
domain = result.domain.value
```

---

#### 2. **Memory Summary** (`agent.py:_memory_update_node`)
**Input:**
- Prompt: "Summarize the following conversation..."
- Message: `HumanMessage(content=prompt_sum)`

**Output:**
- Raw text: `getattr(resp, "content", "").strip()`

**Probléma:** ❌ Nincs strukturált output
**Javítandó:**
```python
class MemorySummary(BaseModel):
    summary: str  # 3-4 sentences
    key_decisions: List[str]
    user_constraints: List[str]

structured_llm = self.llm.with_structured_output(MemorySummary)
result = await structured_llm.ainvoke([HumanMessage(content=prompt_sum)])
state["memory_summary"] = result.summary
state["memory_decisions"] = result.key_decisions
```

---

#### 3. **Memory Facts Extraction** (`agent.py:_memory_update_node`)
**Input:**
- Prompt: "Extract up to 5 atomic facts..."
- Message: `HumanMessage(content=prompt_facts)`

**Output:**
- Raw text parsing:
```python
raw = getattr(resp2, "content", "")
lines = [line.strip("- •\t ") for line in raw.splitlines() if line.strip()]
```

**Probléma:** ❌ Manual parsing, brittle (függ a formázástól)
**Javítandó:**
```python
class MemoryFacts(BaseModel):
    facts: List[str] = Field(..., max_length=5)

structured_llm = self.llm.with_structured_output(MemoryFacts)
result = await structured_llm.ainvoke([HumanMessage(content=prompt_facts)])
state["memory_facts"] = result.facts
```

---

#### 4. **RAG Generation** (`agent.py:_generation_node`)
**Input:**
- Complex multi-part prompt:
  - Memory block (summary + facts)
  - Retrieved documents
  - Domain-specific instructions
  - User query

**Output:**
- Raw text: `response.content`
- Manual section ID extraction for IT domain:
```python
match = re.search(r"([A-Z]+-KB-\d+)", citation["content"])
```

**Probléma:** ❌ Legnagyobb kockázat! Nincs strukturált output
**Javítandó:**
```python
class RAGResponse(BaseModel):
    answer: str
    citations_used: List[str]  # ["IT-KB-234", "IT-KB-567"]
    confidence: float
    language: Literal["hu", "en"]
    
    @validator('citations_used')
    def validate_citations(cls, v):
        pattern = r'^[A-Z]+-KB-\d+$'
        for cite in v:
            if not re.match(pattern, cite):
                raise ValueError(f"Invalid citation format: {cite}")
        return v

structured_llm = self.llm.with_structured_output(RAGResponse)
result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
answer = result.answer
citations = result.citations_used
```

---

## 🎯 Prioritás Javítások

### CRITICAL (Azonnal implementálandó)

#### 1. **RAG Generation** - Strukturált Output
**Miért kritikus:**
- Központi válasz generálás
- Citation formátum validálás
- IT domain guardrail könnyebb validálás

**Implementáció:**
```python
from pydantic import BaseModel, Field, validator
from typing import List, Literal

class RAGGenerationOutput(BaseModel):
    """Structured output for RAG answer generation."""
    answer: str = Field(..., description="Complete answer in Hungarian or English")
    section_ids: List[str] = Field(default_factory=list, description="Section IDs cited (e.g., IT-KB-234)")
    language: Literal["hu", "en"] = Field(..., description="Response language")
    confidence: float = Field(ge=0.0, le=1.0, description="Answer confidence 0-1")
    
    @validator('section_ids', each_item=True)
    def validate_section_id(cls, v):
        if not re.match(r'^[A-Z]+-KB-\d+$', v):
            raise ValueError(f"Invalid section ID format: {v}")
        return v
```

**Használat agent.py-ban:**
```python
async def _generation_node(self, state: AgentState) -> AgentState:
    # ... prompt building ...
    
    # Add structured output instruction to prompt
    prompt += """

Return your response in the following JSON format:
{
    "answer": "Your complete answer here",
    "section_ids": ["IT-KB-234", "IT-KB-567"],  // List all section IDs you reference
    "language": "hu",  // or "en"
    "confidence": 0.85  // Your confidence in the answer (0-1)
}
"""
    
    # Use structured output
    structured_llm = self.llm.with_structured_output(RAGGenerationOutput)
    result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    
    state["output"] = {
        "domain": state["domain"],
        "answer": result.answer,
        "citations": state["citations"],
        "section_ids": result.section_ids,
        "confidence": result.confidence
    }
    
    state["llm_response"] = result.answer
    state["messages"].append(AIMessage(content=result.answer))
```

---

#### 2. **Intent Detection** - Enum Output
**Implementáció:**
```python
class IntentOutput(BaseModel):
    domain: DomainType
    confidence: float = Field(ge=0.0, le=1.0)

async def _intent_detection_node(self, state: AgentState) -> AgentState:
    # ... keyword pre-classification ...
    
    prompt = f"""
Classify this query into ONE category. Return JSON with domain and confidence.

Categories:
- marketing: brand, logo, visual design, arculat
- hr: vacation, employee, szabadság
- it: VPN, computer, software
- finance: invoice, expense, számla
- legal: contract, szerződés
- general: other

Query: "{state['query']}"

Return JSON:
{{
    "domain": "marketing",  // one of: marketing, hr, it, finance, legal, general
    "confidence": 0.9  // 0.0 to 1.0
}}
"""
    
    structured_llm = self.llm.with_structured_output(IntentOutput)
    result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    
    state["domain"] = result.domain.value
    state["intent_confidence"] = result.confidence
```

---

#### 3. **Memory Extraction** - Structured Lists
**Implementáció:**
```python
class MemoryUpdate(BaseModel):
    summary: str = Field(..., max_length=500, description="3-4 sentence summary")
    facts: List[str] = Field(default_factory=list, max_items=5)
    key_decisions: List[str] = Field(default_factory=list, max_items=3)

async def _memory_update_node(self, state: AgentState) -> AgentState:
    transcript = "\n".join(format_msg(m) for m in msgs)
    
    prompt = f"""
Analyze this conversation and extract:
1. A brief summary (3-4 sentences)
2. Up to 5 atomic facts
3. Up to 3 key decisions made

Conversation:
{transcript}

Return JSON:
{{
    "summary": "...",
    "facts": ["fact1", "fact2", ...],
    "key_decisions": ["decision1", ...]
}}
"""
    
    structured_llm = self.llm.with_structured_output(MemoryUpdate)
    result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    
    state["memory_summary"] = result.summary
    state["memory_facts"] = result.facts
    state["memory_decisions"] = result.key_decisions
```

---

## 📊 Összehasonlítás

| Komponens | Jelenlegi | Strukturált | Előnyök |
|-----------|-----------|-------------|---------|
| **Intent Detection** | `response.content.strip()` | `IntentOutput.domain` | Type safety, validálás |
| **Memory Summary** | Text parsing | `MemoryUpdate.summary` | Konzisztens formátum |
| **Memory Facts** | Manual `splitlines()` | `MemoryUpdate.facts` | Nincs parsing hiba |
| **RAG Generation** | Raw text + regex | `RAGGenerationOutput` | Citation validálás, könnyebb guardrail |

---

## 🔧 Implementációs Lépések

### 1. Alapvető Pydantic modellek létrehozása
```bash
# Create new file
backend/domain/llm_outputs.py
```

**Tartalom:**
```python
"""Structured output models for LLM responses."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, validator
import re

from domain.models import DomainType


class IntentOutput(BaseModel):
    """Intent detection structured output."""
    domain: DomainType
    confidence: float = Field(ge=0.0, le=1.0)


class MemoryUpdate(BaseModel):
    """Memory extraction structured output."""
    summary: str = Field(..., max_length=500)
    facts: List[str] = Field(default_factory=list, max_items=5)
    key_decisions: List[str] = Field(default_factory=list, max_items=3)


class RAGGenerationOutput(BaseModel):
    """RAG answer generation structured output."""
    answer: str = Field(..., description="Complete answer")
    section_ids: List[str] = Field(
        default_factory=list,
        description="Section IDs referenced (e.g., IT-KB-234)"
    )
    language: Literal["hu", "en"]
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    
    @validator('section_ids', each_item=True)
    def validate_section_id(cls, v):
        """Validate section ID format: DOMAIN-KB-NUMBER"""
        if v and not re.match(r'^[A-Z]+-KB-\d+$', v):
            raise ValueError(f"Invalid section ID format: {v}")
        return v
```

### 2. Agent.py frissítése
- Import új modellek
- `with_structured_output()` használata minden LLM híváshoz
- Remove manual parsing logic

### 3. Error handling frissítése
```python
from pydantic import ValidationError

try:
    result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
except ValidationError as e:
    logger.error(f"LLM output validation failed: {e}")
    # Fallback vagy retry logic
```

### 4. Tesztek írása
```python
# tests/test_llm_outputs.py
def test_rag_output_validation():
    # Valid
    output = RAGGenerationOutput(
        answer="Test answer",
        section_ids=["IT-KB-123"],
        language="hu",
        confidence=0.9
    )
    assert output.section_ids[0] == "IT-KB-123"
    
    # Invalid section ID
    with pytest.raises(ValidationError):
        RAGGenerationOutput(
            answer="Test",
            section_ids=["invalid-format"],
            language="hu"
        )
```

---

## ✅ Elvárt Eredmények

1. **Type Safety:** Compile-time type checking minden LLM output-ra
2. **Validation:** Automatikus formátum ellenőrzés (section IDs, domain enum)
3. **Könnyebb Debugging:** Structured data könnyebb log-olni és elemezni
4. **Guardrail Egyszerűsítés:** IT domain validation egyszerűbb structured output-tal
5. **Tesztelhetőség:** Mock objects könnyebb Pydantic modellekkel

---

## 🚨 Migráció Stratégia

### Phase 1: RAG Generation (1-2 óra)
1. Create `RAGGenerationOutput` model
2. Update `_generation_node` to use structured output
3. Remove manual regex parsing for section IDs
4. Update guardrail node to use `result.section_ids`

### Phase 2: Intent & Memory (1 óra)
1. Create `IntentOutput` and `MemoryUpdate` models
2. Update `_intent_detection_node`
3. Update `_memory_update_node`
4. Remove manual string parsing

### Phase 3: Testing & Validation (30 perc)
1. Add unit tests for Pydantic models
2. Integration tests with mocked LLM
3. End-to-end test

**Teljes migráció idő:** ~3-4 óra

---

## 📝 Notes

- LangChain 0.1.x támogatja `with_structured_output()` metódust
- OpenAI `gpt-4o-mini` native JSON mode support
- Pydantic v2 gyorsabb validálás
- Backward compatibility: fallback to text parsing error esetén
