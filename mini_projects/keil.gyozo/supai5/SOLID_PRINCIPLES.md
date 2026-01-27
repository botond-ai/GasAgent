# SOLID Principles in FleetAPI Agent

This document explains how SOLID design principles are applied in the FleetAPI Agent backend.

## 1. Single Responsibility Principle (SRP)

**Definition**: A class should have only one reason to change.

### Application in FleetAPI

Each module/class has a single, well-defined responsibility:

#### `app/domain/models.py` - Data Models
```python
@dataclass
class Message:
    """Represents a single message."""
    role: MessageRole
    content: str
    # Only responsible for message structure and serialization
    
    def to_dict(self) -> Dict:
        """Serialize message"""
```

**Responsibility**: Data structure definition and serialization.

#### `app/infrastructure/repository.py` - Data Persistence
```python
class UserRepository:
    """Repository for user profile persistence."""
    
    def get_user_profile(self, user_id: str):
        """Only handles file I/O operations"""
    
    def save_user_profile(self, user_id: str, profile: Dict):
        """Only handles file persistence"""
```

**Responsibility**: File I/O and persistence only.

#### `app/infrastructure/tools.py` - External Integrations
```python
class WeatherTool:
    """Tool for fetching weather data."""
    
    async def fetch_weather(self, lat: float, lon: float):
        """Only handles external API calls"""
```

**Responsibility**: External API integration only.

#### `app/services/agent_service.py` - Business Logic
```python
class AgentService:
    """Service for managing agent interactions."""
    
    async def process_chat(self, request: ChatRequest):
        """Orchestrates agent workflow"""
    
    async def _run_agent(self, message: str, memory: Memory):
        """Agent decision logic"""
```

**Responsibility**: Business logic and workflow orchestration.

#### `app/api/routes.py` - HTTP API
```python
@router.post("/chat")
async def chat(request: ChatRequestBody):
    """HTTP endpoint for chat"""
    # Only handles HTTP concerns (request/response)
```

**Responsibility**: HTTP request/response handling only.

### Benefits
- ✅ Easy to test (each class has one job to test)
- ✅ Easy to maintain (changes affect only one area)
- ✅ Easy to extend (add new tools without touching existing code)

---

## 2. Open/Closed Principle (OCP)

**Definition**: Software entities should be open for extension but closed for modification.

### Application in FleetAPI

#### Tool Extension Pattern

The system is open for extending tools without modifying existing code:

```python
# Existing code - CLOSED for modification
class AgentService:
    def __init__(self, ...):
        self.weather_tool = WeatherTool()
        self.fx_tool = FXTool()
        # No need to change agent logic to add new tools

# Extension - OPEN for extension
class NewLocationWeatherTool:
    """New tool extending functionality"""
    
    async def fetch_weather_by_location(self, location: str):
        # New capability without modifying existing code
        pass

# Add to services layer without changing agent logic
class AgentService:
    def __init__(self, ...):
        self.new_tool = NewLocationWeatherTool()  # Just add it
```

#### Repository Abstraction

The persistence layer is closed for modification but open for extension:

```python
# Current implementation - FILE-BASED (CLOSED)
class UserRepository:
    def __init__(self, data_dir: str = "data/users"):
        self.data_dir = Path(data_dir)
    
    def get_user_profile(self, user_id: str):
        # File-based implementation

# Future extension - DATABASE-BASED (OPEN)
class DatabaseUserRepository:
    """New implementation using database"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_user_profile(self, user_id: str):
        # Database-based implementation
        # Same interface, different implementation

# Usage in AgentService - NO CHANGES NEEDED
class AgentService:
    def __init__(self, user_repo: UserRepository, ...):
        # Works with any UserRepository implementation
        self.user_repo = user_repo
```

### Benefits
- ✅ Add new tools/features without changing existing code
- ✅ Reduces risk of breaking existing functionality
- ✅ Enables database migration without touching business logic

---

## 3. Liskov Substitution Principle (LSP)

**Definition**: Derived classes must be substitutable for their base classes.

### Application in FleetAPI

#### Tool Interface Consistency

All tools follow the same pattern and can be used interchangeably:

```python
# All tools follow consistent interface
class WeatherTool:
    async def fetch_weather(self, ...) -> Dict[str, Any]:
        # Returns structured result with success/error handling
        try:
            result = await api_call()
            return {"success": True, "data": result}
        except ToolError:
            return {"success": False, "error": ...}

class CryptoTool:
    async def get_crypto_price(self, ...) -> Dict[str, Any]:
        # Same interface pattern
        try:
            result = await api_call()
            return {"success": True, "price": result}
        except ToolError:
            return {"success": False, "error": ...}

# Substitutable usage
class AgentService:
    def __init__(self, weather_tool, crypto_tool):
        # Both implement same interface
        # Can be used interchangeably
        self.tools = [weather_tool, crypto_tool]

# Benefit: Add new tools with same interface
class IPGeoTool:
    async def geolocate_ip(self, ip: str) -> Dict[str, Any]:
        # Same interface = automatically works with agent
```

#### Message Role Handling

```python
class Message:
    # Can be USER, ASSISTANT, SYSTEM, or TOOL
    role: MessageRole
    
    # All role types follow same serialization interface
    def to_dict(self) -> Dict[str, Any]:
        # Works for all message types
        
    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        # Works for all message types

# Substitutable in any message context
def process_message(message: Message):
    # Works with any message role
    serialized = message.to_dict()
    displayed = display(serialized)
```

### Benefits
- ✅ Tools are interchangeable
- ✅ New tools automatically compatible with agent
- ✅ Reduces conditional logic for different tool types

---

## 4. Interface Segregation Principle (ISP)

**Definition**: Clients should not be forced to depend on interfaces they don't use.

### Application in FleetAPI

#### Repository Segregation

```python
# Avoid: One monolithic interface
class BadRepository:
    def get_user(self, user_id): pass
    def save_user(self, user_id, data): pass
    def get_session(self, session_id): pass
    def save_session(self, session_id, data): pass
    def search_sessions(self, query): pass

# Better: Segregated interfaces
class UserRepository:
    """Interface for user operations only"""
    def get_user_profile(self, user_id: str): pass
    def save_user_profile(self, user_id: str, profile: Dict): pass
    def create_default_profile(self, user_id: str): pass

class SessionRepository:
    """Interface for session operations only"""
    def get_session(self, session_id: str): pass
    def save_session(self, session_id: str, session: Dict): pass
    def create_empty_session(self, session_id: str, user_id: str): pass
    def search_sessions(self, query: str): pass

# Client depends only on what it needs
class AgentService:
    def __init__(self, user_repo: UserRepository, session_repo: SessionRepository):
        # Each repository has focused interface
        # No unnecessary dependencies
```

#### Tool Segregation

```python
# Each tool is a separate interface
class WeatherTool:
    """Only weather operations"""
    async def fetch_weather(self, lat: float, lon: float): pass

class GeocodingTool:
    """Only geocoding operations"""
    async def geocode(self, address: str): pass
    async def reverse_geocode(self, lat: float, lon: float): pass

class CryptoTool:
    """Only crypto operations"""
    async def get_crypto_price(self, crypto_id: str, currency: str): pass

# Agent depends only on needed tools
class AgentService:
    def __init__(self, weather_tool, crypto_tool):
        # Only what's needed, nothing extra
        self.weather_tool = weather_tool
        self.crypto_tool = crypto_tool
```

### Benefits
- ✅ Minimal dependencies
- ✅ Easy to mock/test (implement only what you need)
- ✅ Flexible - can add/remove tools without affecting others
- ✅ Better separation of concerns

---

## 5. Dependency Inversion Principle (DIP)

**Definition**: Depend on abstractions, not concretions. High-level modules should not depend on low-level modules.

### Application in FleetAPI

#### Repository Abstraction

```python
# Bad: Direct dependency on concrete repository
class BadAgentService:
    def __init__(self):
        # Tightly coupled to file-based repository
        self.user_repo = UserRepository("data/users")
    
    # Can't easily switch to database

# Good: Depend on abstraction (injected)
class AgentService:
    def __init__(
        self,
        user_repo: UserRepository,  # Abstraction/interface
        session_repo: SessionRepository,
        file_storage: FileStorage,
        openai_api_key: str,
    ):
        # High-level module (AgentService) depends on
        # abstractions (Repository interfaces)
        # Low-level details (file I/O) are hidden
        self.user_repo = user_repo
        self.session_repo = session_repo

# Instantiation in main.py:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Concrete implementations created here
    user_repo = UserRepository(data_dir="data/users")
    session_repo = SessionRepository(data_dir="data/sessions")
    
    # Injected into high-level module
    agent_service = AgentService(
        user_repo=user_repo,
        session_repo=session_repo,
        ...
    )
    
    yield
```

#### Tool Abstraction

```python
# Tools follow similar patterns but don't share formal interface
class WeatherTool:
    async def fetch_weather(self, lat, lon) -> Dict:
        # Concrete implementation

class CryptoTool:
    async def get_crypto_price(self, crypto, currency) -> Dict:
        # Concrete implementation

# AgentService depends on tool instances
# Not on specific tool implementations
class AgentService:
    def __init__(self, weather_tool, crypto_tool, ...):
        # Depends on injected tools
        # Can use mocks in testing
        self.weather_tool = weather_tool
        self.crypto_tool = crypto_tool
        
    async def _run_agent(self, message: str, ...):
        # Uses injected tools
        result = await self.weather_tool.fetch_weather(lat, lon)
```

#### Testing Benefits

```python
# Unit test - inject mock repositories
@pytest.fixture
def mock_user_repo():
    class MockUserRepository:
        def get_user_profile(self, user_id: str):
            return {"user_id": user_id, "language": "hu"}
    return MockUserRepository()

@pytest.fixture
def agent_service(mock_user_repo):
    return AgentService(
        user_repo=mock_user_repo,  # Mock, not real
        session_repo=MockSessionRepository(),
        ...
    )

async def test_process_chat(agent_service):
    # Test with mocks - no file I/O
    result = await agent_service.process_chat(...)
    assert result["final_answer"]
```

### Benefits
- ✅ Easy to test (inject mocks)
- ✅ Easy to refactor (switch implementations)
- ✅ Loose coupling between modules
- ✅ Flexible deployment (different implementations for different environments)

---

## Architecture Layer Diagram

```
┌─────────────────────────────────────────────┐
│  API LAYER (Requests/Responses)             │
│  routes.py - HTTP endpoints                 │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  SERVICES LAYER (Business Logic)            │
│  agent_service.py - Workflow orchestration  │
│  - Depends on repositories & tools          │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼────────────┐ ┌─────▼──────────────┐
│ INFRASTRUCTURE     │ │ DOMAIN             │
│ LAYER              │ │ LAYER              │
│ repository.py      │ │ models.py          │
│ tools.py           │ │ (DTOs, entities)   │
│ (Low-level)        │ │ (High-level)       │
└────────────────────┘ └────────────────────┘
```

**Dependency Flow** (from high to low level):
```
API → Services → Infrastructure & Domain
      ↓
      (Inversion: Services depend on abstractions)
```

---

## Summary Table

| Principle | What | Where | How |
|-----------|------|-------|-----|
| **SRP** | Each class one job | Every class | Separated concerns |
| **OCP** | Extend without modify | Tools pattern | Add new tools without changes |
| **LSP** | Substitutable implementations | Tools, Messages | Same interface pattern |
| **ISP** | Segregated interfaces | Repositories, Tools | Focused single-purpose classes |
| **DIP** | Depend on abstractions | AgentService | Dependency injection |

---

## How to Extend the System (Following SOLID)

### Add a New Tool

1. **Create tool class** (Segregated Interface):
```python
# infrastructure/tools.py
class NewTool:
    async def execute(self, param: str) -> Dict:
        # Implementation
```

2. **Add to AgentService** (Dependency Injection):
```python
class AgentService:
    def __init__(self, new_tool: NewTool, ...):  # DIP
        self.new_tool = new_tool  # ISP
```

3. **Use in _run_agent**:
```python
async def _run_agent(self, message: str, ...):
    if "keyword" in message.lower():
        result = await self.new_tool.execute(param)  # LSP
```

**SOLID Benefits**:
- ✅ No changes to existing classes (OCP)
- ✅ Single responsibility per class (SRP)
- ✅ Injected dependency (DIP)
- ✅ Segregated interface (ISP)

---

## Design Pattern Usage

### Dependency Injection
- **Location**: `main.py` lifespan function
- **Benefit**: Loose coupling, testability

### Repository Pattern
- **Location**: `infrastructure/repository.py`
- **Benefit**: Abstraction over data source (file/db)

### Service Layer Pattern
- **Location**: `services/agent_service.py`
- **Benefit**: Centralized business logic

### Data Transfer Object (DTO)
- **Location**: `domain/models.py`
- **Benefit**: Clear contracts between layers

---

## Testing Guidelines (Enabled by SOLID)

```python
# Mock repositories for testing
class MockUserRepository:
    def get_user_profile(self, user_id):
        return {...}

# Mock tools for testing
class MockWeatherTool:
    async def fetch_weather(self, lat, lon):
        return {"current_temp": 5, ...}

# Inject mocks into service
service = AgentService(
    user_repo=MockUserRepository(),
    session_repo=MockSessionRepository(),
    file_storage=MockFileStorage(),
    weather_tool=MockWeatherTool(),
    ...
)

# Test business logic without I/O
assert await service.process_chat(...) == expected
```

---

## Conclusion

FleetAPI Agent demonstrates how SOLID principles lead to:
- **Maintainability**: Clear, focused classes
- **Testability**: Easy to mock and test
- **Extensibility**: Add features without breaking existing code
- **Flexibility**: Swap implementations (file ↔ database)
- **Scalability**: Clean architecture supports growth

Each principle works together to create a robust, professional-grade architecture suitable for educational demonstrations and real-world applications.
