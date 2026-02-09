"""
Structured output models for LLM responses.
Ensures type safety and validation for all LLM interactions.
"""
from typing import List, Literal
from pydantic import BaseModel, Field, field_validator
import re

from domain.models import DomainType


class IntentOutput(BaseModel):
    """Intent detection structured output."""
    domain: DomainType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(default="", description="Brief explanation of classification")


class MemoryUpdate(BaseModel):
    """Memory extraction structured output."""
    summary: str = Field(..., max_length=500, description="3-4 sentence conversation summary")
    facts: List[str] = Field(default_factory=list, description="Up to 5 atomic facts")
    key_decisions: List[str] = Field(default_factory=list, description="Up to 3 key user decisions")
    
    @field_validator('facts')
    @classmethod
    def limit_facts(cls, v):
        """Limit facts to 5 items."""
        return v[:5] if v else []
    
    @field_validator('key_decisions')
    @classmethod
    def limit_decisions(cls, v):
        """Limit decisions to 3 items."""
        return v[:3] if v else []


class RAGGenerationOutput(BaseModel):
    """RAG answer generation structured output with citation validation."""
    answer: str = Field(..., description="Complete answer in Hungarian or English")
    section_ids: List[str] = Field(
        default_factory=list,
        description="Section IDs referenced (e.g., IT-KB-234, HR-KB-456)"
    )
    language: Literal["hu", "en"] = Field(..., description="Response language")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="Answer confidence score")
    
    @field_validator('section_ids')
    @classmethod
    def validate_section_ids(cls, v):
        """Validate section ID format: DOMAIN-KB-NUMBER"""
        pattern = r'^[A-Z]+-KB-\d+$'
        validated = []
        for sid in v:
            if sid and re.match(pattern, sid):
                validated.append(sid)
            elif sid:  # Invalid format, log warning but don't fail
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Invalid section ID format: {sid}, skipping")
        return validated
