# Using Pydantic v2 in the Application

## Overview

**Pydantic v2** is a powerful Python library for data validation and settings management using type annotations. In our application, Pydantic v2 plays a central role in defining type-safe data models, performing runtime validation, and generating API documentation.

## What Is Pydantic v2?

Pydantic v2 provides:

* **Type-safe data models** using Python classes with full type hints
* **Automatic runtime validation** with detailed error messages
* **JSON serialization/deserialization** with custom control
* **FastAPI integration** for automatic OpenAPI documentation
* **Default values** and **factory functions** for flexible model instantiation
* **Custom validation rules** via `field_validator` decorator
* **Configuration management** via `ConfigDict`
* **Performance improvements** with Rust backend (pydantic-core)

## Pydantic in the Application

### Primary Usage Areas

```
1. Domain models (domain/models.py)
   └─> Business entities: Message, UserProfile, ChatRequest, ChatResponse

2. RAG models (rag/models.py)
   └─> Document and chunk models: Document, Chunk, RetrievalResult

3. Configuration models (rag/config.py)
   └─> RAG settings: RAGConfig, ChunkingConfig, EmbeddingConfig

4. FastAPI request/response models (main.py)
   └─> API endpoint schemas and validation

5. Tool argument schemas (services/tools.py)
   └─> LangChain tool parameters
```

## 1. Core Model Patterns

### File: `backend/app/models/schemas.py`

Domain models represent the core business entities of the application.

### Message Model with Validation

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal, Optional, Dict, Any

class Message(BaseModel):
    """A single message in a conversation."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('content')
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Validate that content is not empty."""
        if not v.strip():
            raise ValueError('content cannot be empty or whitespace')
        return v.strip()

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is one of allowed values."""
        allowed = {"user", "assistant", "system", "tool"}
        if v not in allowed:
            raise ValueError(f'role must be one of {allowed}')
        return v
```

**Pydantic v2 Best Practices:**

* Use `@field_validator` decorator instead of old `@validator`
* `field_validator` is mode-aware and supports `mode='before'`, `mode='after'`, `mode='wrap'`
* `Literal` provides strict enum-like validation
* `Field(default_factory=...)` ensures each instance gets a new object

**Usage:**

```python
# Valid message with auto-populated timestamp
message = Message(role="user", content="  Hello!  ")
print(message.content)  # "Hello!" (stripped by validator)
print(message.timestamp)  # Current datetime

# Validation examples
# ✅ Valid
Message(role="assistant", content="Response")

# ❌ Invalid role
try:
    Message(role="invalid", content="Hi")
except ValueError as e:
    print(e)  # role must be one of {...}

# ❌ Empty content
try:
    Message(role="user", content="   ")
except ValueError as e:
    print(e)  # content cannot be empty or whitespace
```

### UserProfile Model with ConfigDict

```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class UserProfile(BaseModel):
    """User profile for persistent storage."""
    # Pydantic v2 configuration using ConfigDict
    model_config = ConfigDict(
        from_attributes=True,  # Accept ORM objects (replaces orm_mode)
        str_strip_whitespace=True,  # Auto-strip string fields
        validate_default=True,  # Validate default values
    )

    user_id: str
    language: str = Field(default="hu", description="User's preferred language")
    default_city: str = Field(default="Budapest", description="User's city")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    preferences: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id format."""
        if not v or len(v) < 3:
            raise ValueError('user_id must be at least 3 characters')
        return v
```

**ConfigDict Improvements over old Config:**

* `from_attributes=True` – replaces `orm_mode` for ORM compatibility
* `str_strip_whitespace=True` – auto-strip all string fields
* `validate_default=True` – ensures default values pass validation
* `json_schema_extra` – add custom OpenAPI documentation
* `frozen=True` – make model immutable (like `frozen_fields`)

**Usage:**

```python
# Create from dict
user = UserProfile(user_id="alice_123")

# Create from ORM object with from_attributes=True
# user = UserProfile.model_validate(db_user)

# Serialize to dict (Pydantic v2)
user_dict = user.model_dump()
print(user_dict)

# Serialize to JSON string
user_json = user.model_dump_json(indent=2)

# Get JSON Schema for OpenAPI
schema = UserProfile.model_json_schema()
```

### ChatRequest and ChatResponse with Serialization

```python
from pydantic import BaseModel, Field, field_serializer
from typing import List, Optional

class ChatRequest(BaseModel):
    """Incoming chat request from the frontend."""
    user_id: str
    message: str
    session_id: Optional[str] = None

class RAGContext(BaseModel):
    """RAG context information."""
    documents: List[str] = Field(default_factory=list)
    confidence: float = 0.0

class ChatResponse(BaseModel):
    """Response to the frontend with custom serialization."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "final_answer": "This is the response",
                "tools_used": [],
                "timestamp": "2024-01-23T10:30:00Z"
            }
        }
    )

    final_answer: str
    tools_used: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tools executed during processing"
    )
    memory_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current state of conversation memory"
    )
    logs: Optional[List[str]] = None
    rag_context: Optional[RAGContext] = None
    debug_logs: List[str] = Field(default_factory=list)

    @field_serializer('timestamp', when_used='json')
    def serialize_timestamp(self, value: datetime) -> str:
        """Custom JSON serialization for timestamp."""
        return value.isoformat()
```

**Pydantic v2 Serialization:**

* Use `field_serializer` for custom field serialization
* `mode='plain'` – replace entire serialization
* `mode='wrap'` – wrap the default serialization
* `when_used='json'` – only apply when serializing to JSON

**FastAPI Integration:**

```python
from fastapi import FastAPI
from app.models.schemas import ChatRequest, ChatResponse

app = FastAPI()

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    FastAPI with Pydantic v2 automatically:
    1. Validates incoming JSON against the ChatRequest schema
    2. Deserializes it into a Python object using model_validate
    3. Serializes the ChatResponse into JSON using model_dump_json
    4. Generates OpenAPI (Swagger) documentation from model_json_schema
    """
    result = await chat_service.process(request)
    return ChatResponse(
        final_answer=result["answer"],
        tools_used=result.get("tools", []),
    )
```

---

## 2. Pydantic v2 API Methods (Breaking Changes from v1)

### Serialization Methods

| **Pydantic v1** | **Pydantic v2** | **Purpose** |
|---|---|---|
| `model.dict()` | `model.model_dump()` | Convert to dict |
| `model.json()` | `model.model_dump_json()` | Convert to JSON string |
| `model.json_schema()` | `Model.model_json_schema()` | Get JSON Schema |
| `model.copy(update={})` | `model.model_copy(update={})` | Create copy with updates |
| `model.parse_obj(data)` | `Model.model_validate(data)` | Parse from dict |
| `model.parse_raw(json_str)` | `Model.model_validate_json(json_str)` | Parse from JSON |

### Usage Examples

```python
# Serialize to dict
user_dict = user.model_dump()
print(user_dict)  # {'user_id': 'alice_123', 'language': 'hu', ...}

# Serialize to JSON (exclude some fields)
json_str = user.model_dump_json(exclude={'preferences'})

# Validate from dict
user = UserProfile.model_validate({
    'user_id': 'bob_456',
    'language': 'en'
})

# Validate from JSON
user = UserProfile.model_validate_json('{"user_id": "charlie_789"}')

# Create a copy with updates
updated_user = user.model_copy(update={'language': 'fr'})

# Get JSON Schema for API documentation
schema = UserProfile.model_json_schema()
```

---

## 3. Field Validators (Replacing @validator)

### Basic Field Validation

```python
from pydantic import BaseModel, field_validator
from typing import List

class DocumentRequest(BaseModel):
    """Document upload request."""
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)

    # Validate single field
    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('title cannot be empty')
        return v.strip()

    # Validate field with mode
    @field_validator('tags', mode='before')
    @classmethod
    def normalize_tags(cls, v):
        """Convert comma-separated string to list."""
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',')]
        return v

    # Validate multiple fields
    @field_validator('title', 'content')
    @classmethod
    def no_html(cls, v: str) -> str:
        if '<' in v or '>' in v:
            raise ValueError('HTML not allowed')
        return v
```

### Advanced Validators (mode parameter)

```python
from pydantic import field_validator
from datetime import datetime

class Event(BaseModel):
    """Event with date validation."""
    name: str
    start_date: datetime
    end_date: datetime

    # mode='before': Validate before Pydantic's parsing
    @field_validator('start_date', mode='before')
    @classmethod
    def parse_start_date(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    # mode='after': Validate after Pydantic's parsing (default)
    @field_validator('end_date', mode='after')
    @classmethod
    def validate_end_date(cls, v: datetime) -> datetime:
        if v < datetime.now():
            raise ValueError('end_date cannot be in the past')
        return v

    # mode='wrap': Wrap the default validator
    @field_validator('name', mode='wrap')
    @classmethod
    def validate_name(cls, v, handler):
        # Run default validation first
        v = handler(v)
        # Apply custom logic
        if len(v) > 255:
            raise ValueError('name too long')
        return v
```

---

## 4. ConfigDict - Configuration in Pydantic v2

### Common ConfigDict Options

```python
from pydantic import BaseModel, ConfigDict, Field

class ConfiguredModel(BaseModel):
    """Model with comprehensive Pydantic v2 configuration."""
    model_config = ConfigDict(
        # Validation & Type Coercion
        str_strip_whitespace=True,  # Auto-strip strings
        validate_default=True,  # Validate default values
        validate_assignment=True,  # Validate on attribute assignment
        str_max_length=1000,  # Max string length
        str_min_length=1,  # Min string length

        # Serialization
        exclude_none=False,  # Exclude None values when serializing
        exclude_unset=False,  # Exclude unset fields
        populate_by_name=True,  # Accept both field name and alias

        # JSON Schema
        json_schema_extra={
            "example": {
                "name": "Example",
                "email": "test@example.com"
            }
        },

        # ORM/Database
        from_attributes=True,  # Accept ORM objects (replaces orm_mode)

        # Immutability
        frozen=False,  # Set to True for immutable models
    )

    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="User email address")
```

### ConfigDict with from_attributes (ORM Support)

```python
# Database Model
class UserDB:
    """SQLAlchemy model."""
    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name

# Pydantic Model with from_attributes=True
class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    name: str

# Convert ORM object to Pydantic model
db_user = UserDB(user_id="123", name="Alice")
pydantic_user = UserSchema.model_validate(db_user)
```

---

## 5. Field Serializers (Custom Serialization)

### Basic Serializers

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime

class BlogPost(BaseModel):
    """Blog post with custom timestamp serialization."""
    title: str
    published_at: datetime
    view_count: int

    # Serialize timestamp as ISO format only in JSON
    @field_serializer('published_at', when_used='json')
    def serialize_published_at(self, value: datetime) -> str:
        return value.isoformat()

    # Custom serializer with mode='wrap'
    @field_serializer('view_count', mode='wrap')
    def serialize_view_count(self, value: int, handler, info):
        if info.mode == 'json':
            return f"{value:,}"  # Format with commas in JSON
        return handler(value)  # Default serialization for dict
```

### Serialization Control

```python
# Exclude fields
data = post.model_dump(exclude={'view_count'})

# Include only specific fields
data = post.model_dump(include={'title', 'published_at'})

# Exclude None values
data = post.model_dump(exclude_none=True)

# Exclude unset fields (fields not explicitly set)
data = post.model_dump(exclude_unset=True)

# Custom serialization when converting to JSON
json_str = post.model_dump_json(by_alias=True, exclude_none=True)
```

---

## 6. Computed Fields (Derived Data)

### Using computed_field

```python
from pydantic import BaseModel, computed_field
from datetime import datetime

class User(BaseModel):
    """User with computed full_name field."""
    first_name: str
    last_name: str
    email: str

    @computed_field  # type: ignore[misc]
    @property
    def full_name(self) -> str:
        """Computed field: combination of first and last name."""
        return f"{self.first_name} {self.last_name}"

    @computed_field(mode='serialization')
    @property
    def email_domain(self) -> str:
        """Only included when serializing."""
        return self.email.split('@')[1]

# Usage
user = User(first_name="John", last_name="Doe", email="john@example.com")
print(user.full_name)  # "John Doe" (available as attribute)
print(user.model_dump())
# {'first_name': 'John', 'last_name': 'Doe', 'email': '...', 
#  'full_name': 'John Doe', 'email_domain': 'example.com'}
```

---

## 7. Model Validation Errors

### Handling ValidationError

```python
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    name: str
    age: int

try:
    user = User(name="John", age="not_a_number")
except ValidationError as e:
    # Pydantic v2 provides detailed error information
    print(e.error_count())  # Number of errors
    print(e.errors())  # List of error dicts
    print(e.json())  # Detailed JSON error report

# Output structure:
# [
#   {
#     'type': 'int_parsing',
#     'loc': ('age',),
#     'msg': 'Input should be a valid integer',
#     'input': 'not_a_number'
#   }
# ]
```

---

## 8. Nested Models and Relationships

### Nested Model Validation

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Address(BaseModel):
    """Nested address model."""
    street: str
    city: str
    postal_code: str

    @field_validator('postal_code')
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        if len(v) < 5:
            raise ValueError('postal_code must be at least 5 characters')
        return v

class Person(BaseModel):
    """Person with nested address."""
    name: str
    email: str
    address: Address  # Nested model
    phone_numbers: List[str] = Field(default_factory=list)
    emergency_contact: Optional['Person'] = None  # Self-reference

# Auto-validation of nested models
person = Person(
    name="Alice",
    email="alice@example.com",
    address={
        "street": "123 Main St",
        "city": "Budapest",
        "postal_code": "12345"
    }
)

# Serialize with nested models
print(person.model_dump())  # Includes nested address dict
print(person.model_dump_json())  # Valid JSON with nested objects
```

---

## 9. Best Practices and Migration from v1

### ✅ DO's (Pydantic v2)

```python
# 1. Use ConfigDict instead of Config class
class Model(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

# 2. Use field_validator instead of @validator
@field_validator('field_name')
@classmethod
def validate_field(cls, v):
    return v

# 3. Use model_dump() instead of dict()
data = model.model_dump()

# 4. Use model_validate() instead of parse_obj()
obj = Model.model_validate(data)

# 5. Add descriptions to fields for better OpenAPI docs
field_name: str = Field(..., description="Field description")

# 6. Use Field with constraints for validation
age: int = Field(..., ge=0, le=150, description="User age")

# 7. Use @computed_field for derived data
@computed_field
@property
def derived(self) -> str:
    return computed_value
```

### ❌ DON'Ts (Deprecated in v2)

```python
# ❌ Don't use Config inner class
class Model(BaseModel):
    class Config:
        str_strip_whitespace = True

# ❌ Don't use @validator
@validator('field')
def validate(cls, v):
    return v

# ❌ Don't use dict() or json()
model.dict()  # Use: model.model_dump()
model.json()  # Use: model.model_dump_json()

# ❌ Don't use parse_obj() or parse_raw()
Model.parse_obj(data)  # Use: Model.model_validate(data)
Model.parse_raw(json)  # Use: Model.model_validate_json(json)

# ❌ Don't use orm_mode in Config
# Use: from_attributes=True in ConfigDict

# ❌ Don't use validator with field name in @root_validator
# Use: @model_validator with mode parameter
```

---

## 10. Summary: Pydantic v2 Key Changes

| Feature | Benefit |
|---------|---------|
| **ConfigDict** | Cleaner, type-safe configuration |
| **field_validator** | More flexible validation modes (before/after/wrap) |
| **field_serializer** | Fine-grained control over serialization |
| **model_dump()** | Consistent API for serialization |
| **computed_field** | Derived properties in serialization |
| **from_attributes** | Better ORM integration |
| **Performance** | Rust-backed validation (pydantic-core) |
| **Better errors** | More detailed validation error messages |