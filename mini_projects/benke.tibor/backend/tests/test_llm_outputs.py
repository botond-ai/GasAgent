"""
Unit tests for LLM structured output models.
Tests validation logic and edge cases.
"""
import pytest
from pydantic import ValidationError

from domain.llm_outputs import IntentOutput, MemoryUpdate, RAGGenerationOutput
from domain.models import DomainType


class TestIntentOutput:
    """Tests for IntentOutput model."""
    
    def test_valid_intent_output(self):
        """Test valid intent output creation."""
        output = IntentOutput(
            domain=DomainType.IT,
            confidence=0.95,
            reasoning="Query mentions VPN and computer access"
        )
        assert output.domain == DomainType.IT
        assert output.confidence == 0.95
        assert "VPN" in output.reasoning
    
    def test_confidence_validation(self):
        """Test confidence must be between 0 and 1."""
        # Valid
        IntentOutput(domain=DomainType.HR, confidence=0.0, reasoning="Test reasoning")
        IntentOutput(domain=DomainType.HR, confidence=1.0, reasoning="Test reasoning")
        
        # Invalid
        with pytest.raises(ValidationError):
            IntentOutput(domain=DomainType.HR, confidence=1.5, reasoning="Test")
        
        with pytest.raises(ValidationError):
            IntentOutput(domain=DomainType.HR, confidence=-0.1, reasoning="Test")
    
    def test_domain_enum_validation(self):
        """Test domain must be valid DomainType."""
        # Valid
        for domain in DomainType:
            output = IntentOutput(domain=domain, confidence=0.8, reasoning="Test reasoning")
            assert output.domain == domain
        
        # Invalid - raw string not allowed
        with pytest.raises(ValidationError):
            IntentOutput(domain="invalid_domain", confidence=0.8, reasoning="Test")


class TestMemoryUpdate:
    """Tests for MemoryUpdate model."""
    
    def test_valid_memory_update(self):
        """Test valid memory update creation."""
        output = MemoryUpdate(
            summary="User asked about vacation policy. Discussed 20 days annual leave.",
            facts=["User wants info on vacation", "Company policy: 20 days/year"],
            key_decisions=["Check vacation calendar before booking"]
        )
        assert len(output.summary) > 0
        assert len(output.facts) == 2
        assert len(output.key_decisions) == 1
    
    def test_facts_limit(self):
        """Test facts are limited to 5 items."""
        many_facts = [f"Fact {i}" for i in range(10)]
        output = MemoryUpdate(
            summary="Test",
            facts=many_facts
        )
        assert len(output.facts) == 5
        assert output.facts == many_facts[:5]
    
    def test_decisions_limit(self):
        """Test decisions are limited to 3 items."""
        many_decisions = [f"Decision {i}" for i in range(5)]
        output = MemoryUpdate(
            summary="Test",
            key_decisions=many_decisions
        )
        assert len(output.key_decisions) == 3
        assert output.key_decisions == many_decisions[:3]
    
    def test_empty_lists_allowed(self):
        """Test empty facts and decisions are allowed."""
        output = MemoryUpdate(
            summary="Brief summary",
            facts=[],
            key_decisions=[]
        )
        assert output.facts == []
        assert output.key_decisions == []
    
    def test_summary_max_length(self):
        """Test summary has max length constraint."""
        long_summary = "x" * 600
        with pytest.raises(ValidationError):
            MemoryUpdate(summary=long_summary)


class TestRAGGenerationOutput:
    """Tests for RAGGenerationOutput model."""
    
    def test_valid_rag_output(self):
        """Test valid RAG output creation."""
        output = RAGGenerationOutput(
            answer="A VPN eléréséhez kérjük használja a Cisco AnyConnect klienst.",
            section_ids=["IT-KB-234", "IT-KB-567"],
            language="hu",
            confidence=0.92
        )
        assert "VPN" in output.answer
        assert len(output.section_ids) == 2
        assert output.language == "hu"
        assert output.confidence == 0.92
    
    def test_section_id_format_validation(self):
        """Test section IDs must match DOMAIN-KB-NUMBER pattern."""
        # Valid formats
        valid_ids = ["IT-KB-123", "HR-KB-001", "MARKETING-KB-999"]
        output = RAGGenerationOutput(
            answer="Test answer",
            section_ids=valid_ids,
            language="en",
            confidence=0.8
        )
        assert output.section_ids == valid_ids
    
    def test_invalid_section_id_skipped(self):
        """Test invalid section IDs are skipped (not fail)."""
        mixed_ids = ["IT-KB-123", "invalid-format", "HR-KB-456", "bad"]
        output = RAGGenerationOutput(
            answer="Test answer",
            section_ids=mixed_ids,
            language="en"
        )
        # Only valid IDs remain
        assert output.section_ids == ["IT-KB-123", "HR-KB-456"]
    
    def test_empty_section_ids_allowed(self):
        """Test empty section IDs list is allowed."""
        output = RAGGenerationOutput(
            answer="General answer without citations",
            section_ids=[],
            language="en"
        )
        assert output.section_ids == []
    
    def test_language_validation(self):
        """Test language must be 'hu' or 'en'."""
        # Valid
        RAGGenerationOutput(answer="Test answer with sufficient length", section_ids=[], language="hu")
        RAGGenerationOutput(answer="Test answer with sufficient length", section_ids=[], language="en")
        
        # Invalid
        with pytest.raises(ValidationError):
            RAGGenerationOutput(answer="Test answer long enough", section_ids=[], language="de")
    
    def test_confidence_default_value(self):
        """Test confidence has default value of 0.8."""
        output = RAGGenerationOutput(
            answer="Test answer with sufficient length",
            section_ids=[],
            language="en"
        )
        assert output.confidence == 0.8
    
    def test_confidence_range_validation(self):
        """Test confidence must be between 0 and 1."""
        # Valid
        RAGGenerationOutput(answer="Test answer with length", section_ids=[], language="en", confidence=0.0)
        RAGGenerationOutput(answer="Test answer with length", section_ids=[], language="en", confidence=1.0)
        
        # Invalid
        with pytest.raises(ValidationError):
            RAGGenerationOutput(answer="Test answer enough", section_ids=[], language="en", confidence=1.5)
        
        with pytest.raises(ValidationError):
            RAGGenerationOutput(answer="Test answer enough", section_ids=[], language="en", confidence=-0.1)
    
    def test_section_id_case_sensitive(self):
        """Test section IDs are case-sensitive (uppercase required)."""
        # Valid uppercase
        output = RAGGenerationOutput(
            answer="Test answer with sufficient length",
            section_ids=["IT-KB-123"],
            language="en"
        )
        assert output.section_ids == ["IT-KB-123"]
        
        # Invalid lowercase (should be skipped)
        output = RAGGenerationOutput(
            answer="Test answer with sufficient length",
            section_ids=["it-kb-123"],
            language="en"
        )
        assert output.section_ids == []  # Skipped due to validation
