# LangGraph Workflow - Mermaid Diagramok

## 1. Workflow Graph Topológia

```mermaid
graph TD
    A["🔍 validate_input<br/>(Input validálás)"] --> B["🎯 category_routing<br/>(Kategória LLM döntés)"]
    
    B --> C["🔢 embed_question<br/>(Vektor beágyazás)"]
    
    C --> D["📚 search_category<br/>(ChromaDB keresés)"]
    
    D --> E{{"🔎 evaluate_search<br/>(Minőség értékelés)"}}
    
    E -->|Jó eredmények| F["✓ fallback_search<br/>(Skip - már OK)"]
    E -->|Rossz/Nincs eredmény| F["🔄 fallback_search<br/>(Összes kategóriában)"]
    
    F --> G["🧹 dedup_chunks<br/>(Duplikálódás eltávolítás)"]
    
    G --> H["🤖 generate_answer<br/>(OpenAI LLM)"]
    
    H --> I["✨ format_response<br/>(Citációk formázása)"]
    
    I --> J["✅ END"]
    
    style A fill:#e1f5ff
    style B fill:#e1f5ff
    style C fill:#f0f4c3
    style D fill:#f0f4c3
    style E fill:#fff9c4
    style F fill:#fff9c4
    style G fill:#f0f4c3
    style H fill:#e1f5ff
    style I fill:#f0f4c3
    style J fill:#c8e6c9
```

## 2. State Flow - Adatok Áramlása

```mermaid
graph LR
    subgraph INPUT["Input (WorkflowState)"]
        A["user_id<br/>question<br/>available_categories"]
    end
    
    subgraph ROUTING["Category Routing"]
        B["routed_category<br/>category_confidence<br/>category_reason"]
    end
    
    subgraph EMBEDDING["Embedding & Search"]
        C["question_embedding<br/>context_chunks<br/>search_strategy"]
    end
    
    subgraph GENERATION["Answer Generation"]
        D["final_answer<br/>citation_sources"]
    end
    
    subgraph METADATA["Metadata"]
        E["workflow_steps<br/>error_messages<br/>performance_metrics"]
    end
    
    INPUT --> ROUTING
    ROUTING --> EMBEDDING
    EMBEDDING --> GENERATION
    GENERATION --> METADATA
    
    style INPUT fill:#c8e6c9
    style ROUTING fill:#bbdefb
    style EMBEDDING fill:#fff9c4
    style GENERATION fill:#f0f4c3
    style METADATA fill:#e0bee7
```

## 3. Search Strategy Decision Tree

```mermaid
graph TD
    A["Kategória keresés<br/>végrehajtása"] --> B{Eredmények<br/>száma?}
    
    B -->|>= 3 dokumentum| C{Átlagos<br/>relevancia?}
    B -->|< 3 dokumentum| D["⚠️ Fallback trigger"]
    B -->|0 dokumentum| D
    
    C -->|>= 0.3| E["✅ CATEGORY_BASED<br/>stratégia használata"]
    C -->|< 0.3| D
    
    D --> F["🔄 Keresés az összes<br/>kategóriában"]
    F --> G{Fallback<br/>eredmények?}
    
    G -->|Found| H["✅ FALLBACK_ALL_CATEGORIES<br/>stratégia használata"]
    G -->|Not Found| I["⚠️ No documents found<br/>Generic response"]
    
    E --> J["Deduplication<br/>Answer Generation"]
    H --> J
    I --> J
    
    style A fill:#fff9c4
    style E fill:#c8e6c9
    style H fill:#c8e6c9
    style I fill:#ffccbc
    style J fill:#f0f4c3
```

## 4. Activity Logging Timeline

```mermaid
graph LR
    subgraph T1["Phase 1: Input Validation"]
        A["🔍 Input validálva"]
    end
    
    subgraph T2["Phase 2: Routing & Embedding"]
        B["🎯 Kategória routing<br/>indítása"]
        C["✓ Kategória kiválasztva"]
        D["🔢 Kérdés beágyazása"]
        E["✓ Beágyazás elkészült"]
    end
    
    subgraph T3["Phase 3: Retrieval"]
        F["🔍 Keresés indítása"]
        G["✓ N dokumentum találva"]
        H{Fallback?}
        I["🔄 Fallback keresés"]
        J["✓ Fallback eredmények"]
    end
    
    subgraph T4["Phase 4: Generation"]
        K["🤖 Válasz generálása"]
        L["✓ Válasz elkészült"]
    end
    
    T1 --> T2 --> T3 --> T4
    T3 --> H
    H -->|Nem| K
    H -->|Igen| I --> J --> K
    
    style T1 fill:#e8f5e9
    style T2 fill:#e3f2fd
    style T3 fill:#fff9c4
    style T4 fill:#f3e5f5
```

## 5. Error Handling Flow

```mermaid
graph TD
    A["Workflow Start"] --> B{Input<br/>valid?}
    
    B -->|No| C["Error: Invalid Input"]
    C --> D["error_messages:<br/>Question is empty"]
    D --> END1["❌ Early Exit"]
    
    B -->|Yes| E["Category Routing"]
    E --> F{Category<br/>found?}
    
    F -->|No| G["Warning: No category"]
    G --> H["Fallback to all categories"]
    H --> I["⚠️ Continue workflow"]
    
    F -->|Yes| J["Vector Search"]
    J --> K{Results<br/>found?}
    
    K -->|No| L["Fallback Search"]
    L --> M{Fallback<br/>results?}
    
    M -->|Yes| N["✓ Continue with fallback"]
    M -->|No| O["⚠️ Generic response"]
    
    K -->|Yes| N
    O --> P["Answer Generation"]
    N --> P
    
    P --> Q["✅ Workflow Complete"]
    END1 --> Q
    
    style C fill:#ffccbc
    style D fill:#ffccbc
    style END1 fill:#e57373
    style Q fill:#c8e6c9
```

## 6. Node Dependencies & Interactions

```mermaid
graph TD
    subgraph DEPS["Node Dependencies"]
        A["validate_input"] -.->|Updates workflow_steps| B["State"]
        B -.->|Passes to next| C["category_routing"]
        C -.->|Uses| D["category_router<br/>AsyncMock"]
        C -.->|Updates state| B
        B -.->|Passes to| E["embed_question"]
        E -.->|Uses| F["embedding_service<br/>AsyncMock"]
        E -.->|Updates state| B
        B -.->|Passes to| G["search_category"]
        G -.->|Uses| H["vector_store<br/>AsyncMock"]
        G -.->|Updates state| B
        B -.->|Passes to| I["evaluate_search"]
        I -.->|Updates state| B
        B -.->|Passes to| J["fallback_search"]
        J -.->|Conditional execution| J
        J -.->|Uses| H
        J -.->|Updates state| B
        B -.->|Passes to| K["dedup_chunks"]
        K -.->|Updates state| B
        B -.->|Passes to| L["generate_answer"]
        L -.->|Uses| M["rag_answerer<br/>AsyncMock"]
        L -.->|Updates state| B
        B -.->|Passes to| N["format_response"]
        N -.->|Updates state| B
    end
    
    style DEPS fill:#f5f5f5
    style B fill:#fff9c4,stroke:#fbc02d,stroke-width:3px
```

## 7. API Call Mapping to Nodes

```mermaid
graph LR
    subgraph API["External APIs"]
        A["CategoryRouter<br/>decide_category()"]
        B["EmbeddingService<br/>embed_text()"]
        C["VectorStore<br/>query()"]
        D["RAGAnswerer<br/>generate_answer()"]
    end
    
    subgraph NODES["Workflow Nodes"]
        E["category_routing"]
        F["embed_question<br/>fallback_search"]
        G["search_category<br/>fallback_search"]
        H["generate_answer"]
    end
    
    A --> E
    B --> F
    C --> G
    D --> H
    
    style A fill:#c8e6c9
    style B fill:#c8e6c9
    style C fill:#c8e6c9
    style D fill:#c8e6c9
    style E fill:#bbdefb
    style F fill:#fff9c4
    style G fill:#fff9c4
    style H fill:#f0f4c3
```

## 8. Workflow Execution Timeline (Example)

```mermaid
timeline
    title Workflow Execution Timeline
    section Input Phase
        T+0ms : validate_input : input_validated
    section Routing Phase
        T+50ms : category_routing : 🎯 Category routing started
        T+150ms : category_routing : ✓ Category selected: docs
    section Embedding Phase
        T+160ms : embed_question : 🔢 Question embedding
        T+250ms : embed_question : ✓ Embedding complete
    section Search Phase
        T+260ms : search_category : 🔍 Search in docs
        T+350ms : search_category : ✓ 5 documents found
        T+360ms : evaluate_search : Evaluating search quality
        T+370ms : fallback_search : ⚠️ Low relevance detected
        T+380ms : fallback_search : 🔄 Fallback search started
        T+450ms : fallback_search : ✓ Fallback complete
    section Processing Phase
        T+460ms : dedup_chunks : 🧹 Deduplication
        T+470ms : dedup_chunks : ✓ 8 unique chunks
    section Generation Phase
        T+480ms : generate_answer : 🤖 Generating answer
        T+750ms : generate_answer : ✓ Answer generated
    section Formatting Phase
        T+760ms : format_response : ✨ Formatting response
        T+770ms : format_response : ✅ Complete
```

## 9. State Transitions - DetailedView

```mermaid
stateDiagram-v2
    [*] --> INPUT: receive input
    
    INPUT --> VALIDATE: input received
    VALIDATE --> ROUTING: input validated
    ROUTING --> EMBED: category decided
    EMBED --> SEARCH: question embedded
    SEARCH --> EVAL: search completed
    EVAL --> FB{fallback needed?}
    
    FB -->|No| DEDUP: search was good
    FB -->|Yes| FBSEARCH: fallback triggered
    FBSEARCH --> DEDUP: fallback completed
    
    DEDUP --> GENERATE: chunks deduplicated
    GENERATE --> FORMAT: answer generated
    FORMAT --> [*]: response formatted
    
    note right of VALIDATE
        Checks:
        - Non-empty question
        - Available categories
    end note
    
    note right of ROUTING
        LLM-based decision
        Returns: category + confidence
    end note
    
    note right of EVAL
        Quality metrics:
        - Chunk count
        - Avg similarity
    end note
    
    note right of FB
        Fallback trigger:
        - No results OR
        - Avg similarity < 0.3
    end note
```

## 10. Async/Sync Wrapper Pattern

```mermaid
graph TD
    subgraph SYNC["Sync Node (LangGraph requirement)"]
        A["def search_category_node<br/>(state: WorkflowState)"]
    end
    
    subgraph WRAPPER["Async Wrapper Creation"]
        B["loop = asyncio.new_event_loop()"]
        C["asyncio.set_event_loop(loop)"]
    end
    
    subgraph ASYNC["Async Function (External API)"]
        D["async def async_search_category<br/>(...)"]
        E["result = await vector_store.query(...)"]
    end
    
    subgraph EXECUTION["Execution & Cleanup"]
        F["result = loop.run_until_complete<br/>(async_search_category(...))"]
        G["loop.close()"]
        H["return updated_state"]
    end
    
    A --> WRAPPER
    WRAPPER --> C
    C --> ASYNC
    ASYNC --> E
    E --> EXECUTION
    EXECUTION --> H
    
    style A fill:#e3f2fd
    style D fill:#f3e5f5
    style H fill:#c8e6c9
```

Ezek a diagramok segítik a LangGraph workflow vizualizálását és megértését!
