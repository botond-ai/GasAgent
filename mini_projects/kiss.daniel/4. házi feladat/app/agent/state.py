"""
Pydantic models for agent state management.
Defines strongly-typed state for the LangGraph workflow.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
import hashlib
import uuid

from pydantic import BaseModel, Field, field_validator


class StepStatus(str, Enum):
    """Status of a step in the execution plan."""
    PLANNED = "planned"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class MeetingNotesInput(BaseModel):
    """Input model for meeting notes processing."""
    notes_text: str = Field(..., description="The raw meeting notes text")
    user_timezone: str = Field(default="Europe/Budapest", description="User's timezone")
    calendar_id: str = Field(default="primary", description="Google Calendar ID to use")
    dry_run: bool = Field(default=False, description="If true, don't create calendar event")
    
    def compute_hash(self) -> str:
        """Compute a hash of the notes for deduplication."""
        normalized = " ".join(self.notes_text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class EventDetails(BaseModel):
    """Extracted event details from meeting notes."""
    title: str = Field(default="", description="Event title/summary")
    start_datetime: Optional[datetime] = Field(default=None, description="Event start time")
    end_datetime: Optional[datetime] = Field(default=None, description="Event end time")
    timezone: str = Field(default="Europe/Budapest", description="Event timezone")
    location: Optional[str] = Field(default=None, description="Event location or meeting room")
    attendees: list[str] = Field(default_factory=list, description="List of attendee emails")
    description: Optional[str] = Field(default=None, description="Event description/agenda")
    conference_link: Optional[str] = Field(default=None, description="Video conference link")
    source_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Extraction confidence 0-1")
    extraction_warnings: list[str] = Field(default_factory=list, description="Warnings during extraction")
    
    def is_complete(self) -> bool:
        """Check if event has minimum required fields."""
        return bool(self.title and self.start_datetime and self.end_datetime)
    
    def compute_dedupe_key(self) -> str:
        """Generate deduplication key based on title and start time."""
        key_data = f"{self.title}|{self.start_datetime.isoformat() if self.start_datetime else ''}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    @field_validator('attendees', mode='before')
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [e.strip() for e in v.split(',') if e.strip()]
        return v


class Step(BaseModel):
    """A single step in the execution plan."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Step name")
    tool_name: Optional[str] = Field(default=None, description="Tool to use (if any)")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Step inputs")
    status: StepStatus = Field(default=StepStatus.PLANNED, description="Step status")
    result: Optional[Any] = Field(default=None, description="Step result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    rationale: Optional[str] = Field(default=None, description="Brief rationale for this step (1-3 sentences)")


class CalendarEventResult(BaseModel):
    """Result from Google Calendar event creation."""
    success: bool = Field(default=False)
    event_id: Optional[str] = Field(default=None)
    html_link: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)


class GuardrailResult(BaseModel):
    """Result from guardrail check before tool execution."""
    allow: bool = Field(default=False, description="Whether to allow the operation")
    reasons: list[str] = Field(default_factory=list, description="Reasons for the decision")
    required_questions: list[str] = Field(default_factory=list, description="Questions to ask user")
    duplicate_risk: bool = Field(default=False, description="Potential duplicate detected")
    similar_event_ids: list[str] = Field(default_factory=list, description="IDs of similar events found")


class MeetingSummary(BaseModel):
    """Structured meeting summary."""
    summary: str = Field(default="", description="5-10 line executive summary")
    decisions: list[str] = Field(default_factory=list, description="Key decisions made")
    action_items: list[dict[str, str]] = Field(default_factory=list, description="Action items with owner and due date")
    risks_open_questions: list[str] = Field(default_factory=list, description="Open questions and risks")
    next_meeting_proposal: Optional[str] = Field(default=None, description="Proposed next meeting time")


class FinalAnswer(BaseModel):
    """Final answer returned to user."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    success: bool = Field(default=False)
    
    # Summary section
    summary: str = Field(default="")
    decisions: list[str] = Field(default_factory=list)
    action_items: list[dict[str, str]] = Field(default_factory=list)
    risks_open_questions: list[str] = Field(default_factory=list)
    
    # Event details
    event_details: Optional[EventDetails] = Field(default=None)
    
    # Calendar result
    calendar_event_result: Optional[CalendarEventResult] = Field(default=None)
    
    # If event not created
    questions_for_user: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    
    # Metadata
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dry_run: bool = Field(default=False)


class AgentState(BaseModel):
    """
    Main agent state for the LangGraph workflow.
    Contains all data flowing through the graph.
    """
    # Run metadata
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Input
    input: MeetingNotesInput
    
    # Summary results
    summary: str = Field(default="")
    decisions: list[str] = Field(default_factory=list)
    action_items: list[dict[str, str]] = Field(default_factory=list)
    risks_open_questions: list[str] = Field(default_factory=list)
    
    # Extracted event
    event_details: Optional[EventDetails] = Field(default=None)
    
    # Execution plan
    steps: list[Step] = Field(default_factory=list)
    current_step_index: int = Field(default=0)
    
    # Tool results
    tool_observations: list[dict[str, Any]] = Field(default_factory=list)
    calendar_event_result: Optional[CalendarEventResult] = Field(default=None)
    
    # Guardrail
    guardrail_result: Optional[GuardrailResult] = Field(default=None)
    
    # Error handling
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0)
    
    # Control flags
    needs_replan: bool = Field(default=False)
    needs_user_input: bool = Field(default=False)
    is_complete: bool = Field(default=False)
    
    # Final output
    final_answer: Optional[FinalAnswer] = Field(default=None)
    
    def get_current_step(self) -> Optional[Step]:
        """Get the current step to execute."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def mark_current_step_done(self, result: Any = None):
        """Mark current step as done and advance index."""
        if step := self.get_current_step():
            step.status = StepStatus.DONE
            step.result = result
            self.current_step_index += 1
    
    def mark_current_step_failed(self, error: str):
        """Mark current step as failed."""
        if step := self.get_current_step():
            step.status = StepStatus.FAILED
            step.error = error
            self.errors.append(f"Step '{step.name}' failed: {error}")
    
    def all_steps_done(self) -> bool:
        """Check if all steps are completed."""
        return all(s.status in (StepStatus.DONE, StepStatus.SKIPPED) for s in self.steps)
    
    def has_fatal_error(self) -> bool:
        """Check if there's a fatal error that should stop execution."""
        failed_critical = any(
            s.status == StepStatus.FAILED and s.name in ("ValidateAndNormalizeEventDetails",)
            for s in self.steps
        )
        return failed_critical or len(self.errors) > 5


class PlannerOutput(BaseModel):
    """Output from the Planner node."""
    steps: list[Step]
    rationale: str = Field(default="", description="Brief reasoning for the plan")


class ExtractorOutput(BaseModel):
    """Output from extraction LLM call."""
    title: str = Field(default="")
    date: Optional[str] = Field(default=None, description="Date string (YYYY-MM-DD)")
    time: Optional[str] = Field(default=None, description="Time string (HH:MM)")
    duration_minutes: Optional[int] = Field(default=None)
    timezone: str = Field(default="Europe/Budapest")
    location: Optional[str] = Field(default=None)
    attendees: list[str] = Field(default_factory=list)
    agenda: Optional[str] = Field(default=None)
    conference_link: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class SummarizerOutput(BaseModel):
    """Output from summarization LLM call."""
    summary: str = Field(default="")
    decisions: list[str] = Field(default_factory=list)
    action_items: list[dict[str, str]] = Field(default_factory=list)
    risks_open_questions: list[str] = Field(default_factory=list)
    next_meeting_hint: Optional[str] = Field(default=None)
