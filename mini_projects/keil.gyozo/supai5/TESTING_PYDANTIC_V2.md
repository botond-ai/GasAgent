# Pydantic v2 Integration Testing Guide

## Testing Strategy

Ez a dokumentum tartalmazza a Pydantic v2 refaktorálás validálásához szükséges teszteket.

---

## 1. Model Validation Tests

### Test File: `tests/test_models.py`

```python
"""
Test Pydantic v2 model validations.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime

from app.models.schemas import (
    Citation,
    AnswerDraft,
    Ticket,
    TicketCreate,
    Message,
    UserProfile
)


class TestCitationModel:
    """Test Citation model validation."""

    def test_valid_citation(self):
        """Test creating valid citation."""
        citation = Citation(
            text="Example citation text",
            source="FAQ Document",
            relevance=0.95
        )
        assert citation.text == "Example citation text"
        assert citation.source == "FAQ Document"
        assert citation.relevance == 0.95

    def test_citation_relevance_boundary(self):
        """Test relevance score constraints."""
        # Valid boundaries
        Citation(text="x", source="y", relevance=0.0)
        Citation(text="x", source="y", relevance=1.0)

        # Invalid: over 1.0
        with pytest.raises(ValidationError) as exc:
            Citation(text="x", source="y", relevance=1.5)
        assert "less than or equal to 1.0" in str(exc.value)

    def test_citation_extra_forbid(self):
        """Test that extra fields are forbidden (ConfigDict)."""
        with pytest.raises(ValidationError) as exc:
            Citation(
                text="x",
                source="y",
                relevance=0.5,
                extra_field="not_allowed"  # Should fail
            )
        assert "extra_forbidden" in str(exc.value)

    def test_citation_model_dump(self):
        """Test Pydantic v2 model_dump() method."""
        citation = Citation(
            text="Test",
            source="Source",
            relevance=0.8
        )
        
        # model_dump() replaces dict()
        data = citation.model_dump()
        assert data == {
            "text": "Test",
            "source": "Source",
            "relevance": 0.8
        }

    def test_citation_model_dump_json(self):
        """Test Pydantic v2 model_dump_json() method."""
        citation = Citation(
            text="Test",
            source="Source",
            relevance=0.8
        )
        
        # model_dump_json() replaces json()
        json_str = citation.model_dump_json()
        assert '"text":"Test"' in json_str
        assert '"relevance":0.8' in json_str


class TestAnswerDraftModel:
    """Test AnswerDraft model validation."""

    def test_valid_answer_draft(self):
        """Test creating valid answer draft."""
        draft = AnswerDraft(
            greeting="Hello!",
            body="Here's the solution...",
            closing="Best regards",
            tone="empathetic_professional",
            citations=[]
        )
        assert draft.greeting == "Hello!"
        assert draft.tone == "empathetic_professional"
        assert draft.citations == []

    def test_answer_draft_with_citations(self):
        """Test answer draft with citations."""
        citation = Citation(
            text="Citation text",
            source="Doc A",
            relevance=0.9
        )
        
        draft = AnswerDraft(
            greeting="Hello",
            body="Solution",
            closing="Thanks",
            tone="formal",
            citations=[citation]
        )
        
        assert len(draft.citations) == 1
        assert draft.citations[0].source == "Doc A"

    def test_answer_draft_model_dump(self):
        """Test model_dump with nested Citation objects."""
        citation = Citation(
            text="Citation",
            source="Source",
            relevance=0.8
        )
        
        draft = AnswerDraft(
            greeting="Hi",
            body="Body",
            closing="Close",
            tone="casual",
            citations=[citation]
        )
        
        # model_dump() serializes nested objects
        data = draft.model_dump()
        assert isinstance(data["citations"], list)
        assert data["citations"][0]["text"] == "Citation"


class TestTicketModel:
    """Test Ticket model validation."""

    def test_valid_ticket(self):
        """Test creating valid ticket."""
        ticket = Ticket(
            id="ticket-123",
            customer_name="John Doe",
            customer_email="john@example.com",
            subject="Problem with order",
            message="I have a problem",
            created_at=datetime.now(),
            status="new"
        )
        assert ticket.id == "ticket-123"
        assert ticket.status == "new"

    def test_ticket_status_enum(self):
        """Test status literal type validation."""
        # Valid statuses
        for status in ["new", "processing", "completed", "error"]:
            ticket = Ticket(
                id="x",
                customer_name="x",
                customer_email="x@x.x",
                subject="x",
                message="x",
                created_at=datetime.now(),
                status=status
            )
            assert ticket.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            Ticket(
                id="x",
                customer_name="x",
                customer_email="x@x.x",
                subject="x",
                message="x",
                created_at=datetime.now(),
                status="invalid_status"
            )
```

---

## 2. API Schema Tests

### Test File: `tests/test_api_schemas.py`

```python
"""
Test API schemas with Pydantic v2 ConfigDict.
"""
import pytest
import json
from app.api.documents import (
    DocumentMetadata,
    DocumentStats,
    DocumentUploadResponse
)
from app.api.health import HealthResponse


class TestDocumentMetadata:
    """Test DocumentMetadata schema."""

    def test_valid_metadata(self):
        """Test valid metadata creation."""
        metadata = DocumentMetadata(
            id="doc-123",
            title="FAQ",
            category="Product",
            description="Product FAQ",
            filename="faq.pdf",
            file_type="pdf",
            created_at="2024-01-23T10:30:00Z",
            chunk_count=10
        )
        assert metadata.id == "doc-123"
        assert metadata.chunk_count == 10

    def test_metadata_json_schema(self):
        """Test JSON schema generation (ConfigDict.json_schema_extra)."""
        schema = DocumentMetadata.model_json_schema()
        
        # Check that schema has properties
        assert "properties" in schema
        assert "id" in schema["properties"]
        assert "title" in schema["properties"]
        
        # Check example from json_schema_extra
        assert "example" in schema
        assert schema["example"]["id"] == "doc-123"

    def test_metadata_model_dump(self):
        """Test model_dump() serialization."""
        metadata = DocumentMetadata(
            id="doc-1",
            title="Test",
            category="Cat",
            filename="file.pdf",
            file_type="pdf",
            created_at="2024-01-01T00:00:00Z",
            chunk_count=5
        )
        
        dumped = metadata.model_dump()
        assert dumped["id"] == "doc-1"
        assert dumped["chunk_count"] == 5


class TestDocumentStats:
    """Test DocumentStats schema."""

    def test_valid_stats(self):
        """Test valid stats creation."""
        stats = DocumentStats(
            total_documents=10,
            total_chunks=250,
            categories={"Product": 5, "Billing": 3, "Tech": 2},
            collection_status="ready"
        )
        assert stats.total_documents == 10
        assert stats.categories["Product"] == 5

    def test_stats_json_schema(self):
        """Test JSON schema with ConfigDict."""
        schema = DocumentStats.model_json_schema()
        assert "example" in schema
        assert schema["example"]["total_documents"] == 10


class TestDocumentUploadResponse:
    """Test DocumentUploadResponse schema."""

    def test_successful_upload(self):
        """Test successful upload response."""
        response = DocumentUploadResponse(
            success=True,
            message="Uploaded",
            document=None
        )
        assert response.success is True
        assert response.message == "Uploaded"

    def test_with_document(self):
        """Test response with document metadata."""
        metadata = DocumentMetadata(
            id="doc-1",
            title="Test",
            category="Test",
            filename="test.pdf",
            file_type="pdf",
            created_at="2024-01-01T00:00:00Z",
            chunk_count=5
        )
        
        response = DocumentUploadResponse(
            success=True,
            message="Success",
            document=metadata
        )
        assert response.document is not None
        assert response.document.id == "doc-1"


class TestHealthResponse:
    """Test HealthResponse schema."""

    def test_healthy_response(self):
        """Test healthy status response."""
        response = HealthResponse(
            status="healthy",
            services={
                "redis": "healthy",
                "qdrant": "healthy"
            }
        )
        assert response.status == "healthy"
        assert response.services["redis"] == "healthy"

    def test_degraded_response(self):
        """Test degraded status response."""
        response = HealthResponse(
            status="degraded",
            services={
                "redis": "healthy",
                "qdrant": "unhealthy"
            }
        )
        assert response.status == "degraded"

    def test_json_schema_with_examples(self):
        """Test JSON schema includes examples from ConfigDict."""
        schema = HealthResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["status"] == "healthy"
```

---

## 3. Serialization Tests

### Test File: `tests/test_serialization.py`

```python
"""
Test Pydantic v2 serialization methods.
"""
import json
import pytest
from datetime import datetime
from app.models.schemas import Citation, AnswerDraft


class TestCitationSerialization:
    """Test Citation serialization with v2 methods."""

    def test_model_dump_vs_dict(self):
        """Compare model_dump() vs old dict()."""
        citation = Citation(
            text="Test",
            source="Source",
            relevance=0.8
        )
        
        # Pydantic v2
        dumped = citation.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["text"] == "Test"

    def test_model_dump_json(self):
        """Test model_dump_json() method."""
        citation = Citation(
            text="Test",
            source="Source",
            relevance=0.8
        )
        
        # model_dump_json() returns JSON string
        json_str = citation.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["text"] == "Test"
        assert parsed["relevance"] == 0.8

    def test_model_dump_exclude(self):
        """Test model_dump with field exclusion."""
        citation = Citation(
            text="Test",
            source="Source",
            relevance=0.8
        )
        
        # Exclude specific field
        dumped = citation.model_dump(exclude={'source'})
        assert 'text' in dumped
        assert 'source' not in dumped
        assert 'relevance' in dumped

    def test_model_dump_exclude_none(self):
        """Test model_dump with exclude_none."""
        draft = AnswerDraft(
            greeting="Hi",
            body="Body",
            closing="Close",
            tone="formal",
            citations=[]
        )
        
        # Include None values
        dumped_with_none = draft.model_dump()
        assert any(v is None for v in dumped_with_none.values())

        # Exclude None values
        dumped_no_none = draft.model_dump(exclude_none=True)
        assert not any(v is None for v in dumped_no_none.values())


class TestNestedSerialization:
    """Test serialization of nested Pydantic models."""

    def test_answer_draft_with_citations_dump(self):
        """Test nested Citation serialization."""
        citation1 = Citation(text="Cit1", source="Src1", relevance=0.9)
        citation2 = Citation(text="Cit2", source="Src2", relevance=0.8)
        
        draft = AnswerDraft(
            greeting="Hi",
            body="Body",
            closing="Close",
            tone="formal",
            citations=[citation1, citation2]
        )
        
        # model_dump() handles nested objects
        dumped = draft.model_dump()
        assert isinstance(dumped["citations"], list)
        assert len(dumped["citations"]) == 2
        assert dumped["citations"][0]["text"] == "Cit1"

    def test_nested_model_validate(self):
        """Test model_validate with nested objects."""
        data = {
            "greeting": "Hi",
            "body": "Body",
            "closing": "Close",
            "tone": "formal",
            "citations": [
                {"text": "Cit", "source": "Src", "relevance": 0.9}
            ]
        }
        
        # model_validate() parses from dict
        draft = AnswerDraft.model_validate(data)
        assert len(draft.citations) == 1
        assert isinstance(draft.citations[0], Citation)
        assert draft.citations[0].text == "Cit"
```

---

## 4. Validator Tests

### Test File: `tests/test_validators.py`

```python
"""
Test Pydantic v2 field_validator decorators.
"""
import pytest
from pydantic import ValidationError, BaseModel, field_validator


class TestFieldValidator:
    """Test @field_validator functionality."""

    def test_simple_validator(self):
        """Test basic field_validator."""
        from app.models.schemas import Message

        # Valid message
        msg = Message(role="user", content="Hello")
        assert msg.content == "Hello"

        # Invalid role (Literal validation)
        with pytest.raises(ValidationError) as exc:
            Message(role="invalid", content="Hi")

    def test_validator_with_strip(self):
        """Test validator that strips whitespace."""
        from app.models.schemas import Message

        # Content is stripped by validator
        msg = Message(role="user", content="  Hello  ")
        assert msg.content == "Hello"

    def test_multiple_validators(self):
        """Test multiple validators on same field."""
        class User(BaseModel):
            email: str

            @field_validator('email')
            @classmethod
            def validate_email(cls, v):
                if '@' not in v:
                    raise ValueError('Invalid email')
                return v.lower()

        # Valid email
        user = User(email="John@Example.COM")
        assert user.email == "john@example.com"

        # Invalid email
        with pytest.raises(ValidationError):
            User(email="notanemail")
```

---

## 5. Integration Tests

### Test File: `tests/test_integration_pydantic.py`

```python
"""
Integration tests for Pydantic v2 throughout the application.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import Ticket, TriageResponse
from datetime import datetime

client = TestClient(app)


class TestTicketCreationIntegration:
    """Test ticket creation with model validation."""

    def test_create_ticket_endpoint(self):
        """Test creating ticket via API."""
        response = client.post(
            "/api/tickets/",
            json={
                "customer_name": "John Doe",
                "customer_email": "john@example.com",
                "subject": "Issue",
                "message": "Help needed"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check that response matches Ticket model
        assert "id" in data
        assert data["customer_name"] == "John Doe"
        assert data["status"] == "new"

    def test_invalid_ticket_data(self):
        """Test validation error handling."""
        response = client.post(
            "/api/tickets/",
            json={
                "customer_name": "",  # Empty not allowed
                "customer_email": "invalid-email",  # Invalid format
                "subject": "",  # Empty not allowed
                "message": "x"
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestDocumentUploadIntegration:
    """Test document upload with schema validation."""

    def test_document_metadata_response(self):
        """Test document upload response schema."""
        # This would test actual file upload
        # For now, test the schema
        from app.api.documents import DocumentMetadata
        
        metadata = DocumentMetadata(
            id="doc-1",
            title="Test",
            category="Test",
            filename="test.pdf",
            file_type="pdf",
            created_at="2024-01-01T00:00:00Z",
            chunk_count=5
        )
        
        # model_dump_json() for API response
        json_response = metadata.model_dump_json()
        assert "doc-1" in json_response
        assert "Test" in json_response


class TestHealthCheckIntegration:
    """Test health check endpoint with schema."""

    def test_health_check_response(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check HealthResponse schema
        assert "status" in data
        assert "services" in data
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_models.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/test_models.py::TestCitationModel::test_citation_extra_forbid -v
```

---

## Expected Test Results

✅ All Citation validations pass
✅ All AnswerDraft nested validations pass
✅ model_dump() methods work correctly
✅ model_dump_json() produces valid JSON
✅ ConfigDict json_schema_extra appears in schema
✅ API endpoints return correct response types
✅ Field validators execute properly
✅ Extra fields are forbidden (ConfigDict)

---

## Notes

- A tesztek biztosítják a Pydantic v2 migrálás sikerességét
- Field descriptions javítják az IDE autocomplete-et
- JSON schema example-ek az OpenAPI dokumentációban jelennek meg
- ValidationError-ek v2 formátumban érkeznek
