# SOLID Principles Refactoring Plan

## Current Architecture Analysis

### Issues Identified:

#### 1. **Single Responsibility Principle (SRP) Violations**

**Issue:** `tickets.py` API route handler kezel túl sok felelősséget:
- HTTP request/response handling
- Workflow orchestration
- Caching logic
- Ticket state management

```python
# ❌ PROBLEM: Process endpoint has multiple responsibilities
@router.post("/{ticket_id}/process", response_model=TriageResponse)
async def process_ticket(ticket_id: str, workflow, redis_service):
    # 1. Data validation
    # 2. Cache checking
    # 3. Workflow execution
    # 4. Cache storage
    # 5. State management
```

**Solution:** Create a TicketService layer that handles the business logic

---

#### 2. **Open/Closed Principle (OCP) Violations**

**Issues:**
- `tickets.py` is tightly coupled to specific implementations
- Adding new ticket processors requires modifying existing code
- Workflow is hardcoded into the API

**Current Problem:**
```python
# ❌ Workflow is hardcoded, can't extend without modifying
workflow = Depends(get_workflow)  # Only one workflow type
```

**Solution:** 
- Create TicketProcessor abstraction
- Make ticket processing strategy-based

---

#### 3. **Liskov Substitution Principle (LSP) Issues**

**Issue:** RAG service, workflow nodes, and other tools don't follow consistent patterns

**Solution:**
- Define consistent tool/processor interfaces
- Ensure interchangeability

---

#### 4. **Interface Segregation Principle (ISP) Violations**

**Issue:** Services have too many methods that clients don't need

```python
# ❌ Single large interface
class RAGService:
    async def expand_queries(self): pass
    async def retrieve_documents(self): pass
    async def rerank_documents(self): pass
    # Too many concerns in one interface
```

**Solution:**
- Split RAGService into: QueryExpander, DocumentRetriever, DocumentRanker
- Each client depends only on what it needs

---

#### 5. **Dependency Inversion Principle (DIP) Violations**

**Issue:** Direct coupling to concrete implementations in API routes

```python
# ❌ Tight coupling to concrete implementations
workflow = Depends(get_workflow)  # Depends on concrete SupportWorkflow
redis_service = Depends(get_redis_service)  # Depends on concrete RedisService
```

**Solution:**
- Depend on abstractions (interfaces)
- Inject dependencies
- Create service factory/container

---

## Refactoring Plan

### Phase 1: Create Service Abstractions

#### 1.1 Create TicketService (SRP)
**File:** `backend/app/services/ticket_service.py`

```python
class TicketService:
    """Service for ticket business logic (SRP)."""
    
    def __init__(
        self,
        ticket_repository: 'TicketRepository',
        ticket_processor: 'TicketProcessor',
        cache_service: 'CacheService'
    ):
        # Dependencies injected
        self.repository = ticket_repository
        self.processor = ticket_processor
        self.cache = cache_service
    
    async def create_ticket(self, data: TicketCreate) -> Ticket:
        """Only creates tickets"""
        
    async def get_ticket(self, ticket_id: str) -> Ticket:
        """Only retrieves tickets"""
        
    async def process_ticket(self, ticket_id: str) -> TriageResponse:
        """Only processes tickets"""
        # Orchestrates: fetch → cache check → process → cache → return
```

#### 1.2 Create TicketRepository (ISP)
**File:** `backend/app/infrastructure/repositories.py`

```python
from abc import ABC, abstractmethod

class ITicketRepository(ABC):
    """Interface for ticket persistence (ISP)."""
    
    @abstractmethod
    async def get(self, ticket_id: str) -> Ticket: pass
    
    @abstractmethod
    async def save(self, ticket: Ticket) -> None: pass
    
    @abstractmethod
    async def list(self, status: str = None) -> list[Ticket]: pass

class InMemoryTicketRepository(ITicketRepository):
    """In-memory implementation for development."""
    
    def __init__(self):
        self._storage = {}
    
    async def get(self, ticket_id: str) -> Ticket:
        return self._storage.get(ticket_id)
    
    async def save(self, ticket: Ticket) -> None:
        self._storage[ticket.id] = ticket
```

#### 1.3 Create TicketProcessor Abstraction (OCP)
**File:** `backend/app/services/processors.py`

```python
from abc import ABC, abstractmethod

class ITicketProcessor(ABC):
    """Interface for ticket processing (OCP - open for extension)."""
    
    @abstractmethod
    async def process(self, ticket: Ticket) -> TriageResponse: pass

class WorkflowTicketProcessor(ITicketProcessor):
    """Uses LangGraph workflow."""
    
    def __init__(self, workflow: SupportWorkflow):
        self.workflow = workflow
    
    async def process(self, ticket: Ticket) -> TriageResponse:
        state = {
            "ticket_id": ticket.id,
            "raw_message": ticket.message,
            ...
        }
        final_state = await self.workflow.process_ticket(state)
        return TriageResponse(**final_state.get("output", {}))
```

#### 1.4 Create CacheService Abstraction (DIP)
**File:** `backend/app/services/cache.py`

```python
from abc import ABC, abstractmethod

class ICacheService(ABC):
    """Cache service interface (DIP)."""
    
    @abstractmethod
    async def get(self, key: str) -> Any: pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None) -> None: pass

class RedisCacheService(ICacheService):
    """Redis implementation."""
    
    def __init__(self, redis_client):
        self.client = redis_client
    
    async def get(self, key: str):
        return self.client.get(key)
```

### Phase 2: Update API Routes (SRP)

**File:** `backend/app/api/tickets.py`

```python
# ✅ BEFORE: Complex, multiple responsibilities
@router.post("/{ticket_id}/process")
async def process_ticket(
    ticket_id: str,
    workflow = Depends(get_workflow),
    redis_service = Depends(get_redis_service)
):
    # 1. Cache check
    # 2. Workflow execution
    # 3. Cache storage
    # 4. State management

# ✅ AFTER: Simple, single responsibility
@router.post("/{ticket_id}/process", response_model=TriageResponse)
async def process_ticket(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service)
) -> TriageResponse:
    """HTTP endpoint - only handles HTTP concerns."""
    return await ticket_service.process_ticket(ticket_id)
```

### Phase 3: Update Dependency Injection

**File:** `backend/app/api/dependencies.py`

```python
# ✅ Create services with dependencies
def get_ticket_repository() -> ITicketRepository:
    """Factory for ticket repository."""
    return InMemoryTicketRepository()

def get_cache_service() -> ICacheService:
    """Factory for cache service."""
    return RedisCacheService(redis_client)

def get_ticket_processor() -> ITicketProcessor:
    """Factory for ticket processor."""
    workflow = get_workflow()
    return WorkflowTicketProcessor(workflow)

def get_ticket_service(
    repository: ITicketRepository = Depends(get_ticket_repository),
    processor: ITicketProcessor = Depends(get_ticket_processor),
    cache: ICacheService = Depends(get_cache_service)
) -> TicketService:
    """Compose and inject dependencies (DIP)."""
    return TicketService(
        ticket_repository=repository,
        ticket_processor=processor,
        cache_service=cache
    )
```

### Phase 4: Update Services Layer (ISP)

#### Split RAGService (ISP)

```python
# ❌ BEFORE: One large service
class RAGService:
    async def expand_queries(self): pass
    async def retrieve_documents(self): pass
    async def rerank_documents(self): pass

# ✅ AFTER: Segregated interfaces
class IQueryExpander(ABC):
    @abstractmethod
    async def expand_queries(self, query: str) -> list[str]: pass

class IDocumentRetriever(ABC):
    @abstractmethod
    async def retrieve(self, queries: list[str]) -> list[dict]: pass

class IDocumentRanker(ABC):
    @abstractmethod
    async def rerank(self, documents: list[dict], query: str) -> list[dict]: pass
```

### Phase 5: Workflow Node Segregation (SRP)

```python
# ✅ Each node has ONE responsibility

class DetectIntentNode:
    """Only detects intent."""
    async def execute(self, state: dict) -> dict: pass

class TriageNode:
    """Only triages."""
    async def execute(self, state: dict) -> dict: pass

class RAGNode:
    """Only performs RAG."""
    async def execute(self, state: dict) -> dict: pass

class DraftAnswerNode:
    """Only drafts answer."""
    async def execute(self, state: dict) -> dict: pass
```

---

## File Structure After Refactoring

```
backend/app/
├── api/
│   ├── dependencies.py     # ✅ Dependency injection container
│   ├── routes/
│   │   └── tickets.py      # ✅ Thin HTTP handlers (SRP)
│   └── __init__.py
│
├── services/
│   ├── ticket_service.py   # ✅ NEW: Ticket business logic (SRP)
│   ├── processors.py       # ✅ NEW: TicketProcessor abstraction (OCP)
│   ├── cache.py            # ✅ NEW: Cache abstraction (DIP)
│   ├── rag_service.py      # ✅ REFACTORED: Split into segregated interfaces
│   ├── document_service.py
│   ├── qdrant_service.py
│   ├── redis_service.py
│   └── __init__.py
│
├── infrastructure/
│   ├── repositories.py     # ✅ NEW: Repository abstractions
│   ├── tools.py
│   └── __init__.py
│
├── workflows/
│   ├── graph.py            # Keep as-is
│   ├── nodes.py            # ✅ REFACTORED: One job per node
│   └── __init__.py
│
├── models/
│   └── schemas.py          # Already good (DTOs)
│
└── core/
    └── config.py
```

---

## SOLID Principles Coverage

| Principle | Status | How |
|-----------|--------|-----|
| **SRP** | ✅ | TicketService (only business logic), API routes (only HTTP) |
| **OCP** | ✅ | ITicketProcessor interface allows new processors without changes |
| **LSP** | ✅ | All processors follow ITicketProcessor interface |
| **ISP** | ✅ | Segregated interfaces: IQueryExpander, IDocumentRetriever, IDocumentRanker |
| **DIP** | ✅ | Depend on abstractions, inject concrete implementations |

---

## Benefits

1. **Testability**: Mock any service/repository
2. **Maintainability**: Clear responsibilities
3. **Extensibility**: Add new processors without modifying existing code
4. **Flexibility**: Swap implementations (in-memory ↔ database)
5. **Reusability**: Services can be reused in different contexts

---

## Implementation Steps

1. Create abstraction interfaces (repositories.py, processors.py, cache.py)
2. Create TicketService with dependency injection
3. Refactor API routes to use TicketService
4. Update dependency injection in dependencies.py
5. Split RAGService into segregated services
6. Update tests with mocks
7. Document the new architecture

---

## Backward Compatibility

- Keep existing service signatures
- Gradually migrate routes to new services
- Maintain API contract (request/response format)
- No database schema changes required
