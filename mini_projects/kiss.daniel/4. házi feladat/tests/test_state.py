"""
Unit tests for Pydantic state models.
"""

import pytest
from datetime import datetime, timedelta

from app.agent.state import (
    MeetingNotesInput,
    EventDetails,
    Step,
    StepStatus,
    AgentState,
    CalendarEventResult,
    GuardrailResult,
    FinalAnswer,
)


class TestMeetingNotesInput:
    """Tests for MeetingNotesInput model."""
    
    def test_basic_creation(self):
        """Test basic input creation with defaults."""
        input_data = MeetingNotesInput(notes_text="Test notes")
        
        assert input_data.notes_text == "Test notes"
        assert input_data.user_timezone == "Europe/Budapest"
        assert input_data.calendar_id == "primary"
        assert input_data.dry_run is False
    
    def test_custom_values(self):
        """Test input with custom values."""
        input_data = MeetingNotesInput(
            notes_text="Custom notes",
            user_timezone="America/New_York",
            calendar_id="work",
            dry_run=True,
        )
        
        assert input_data.user_timezone == "America/New_York"
        assert input_data.calendar_id == "work"
        assert input_data.dry_run is True
    
    def test_compute_hash(self):
        """Test hash computation for deduplication."""
        input1 = MeetingNotesInput(notes_text="Test notes")
        input2 = MeetingNotesInput(notes_text="Test notes")
        input3 = MeetingNotesInput(notes_text="Different notes")
        
        # Same text should produce same hash
        assert input1.compute_hash() == input2.compute_hash()
        # Different text should produce different hash
        assert input1.compute_hash() != input3.compute_hash()
    
    def test_hash_normalization(self):
        """Test that hash normalizes whitespace."""
        input1 = MeetingNotesInput(notes_text="Test  notes")
        input2 = MeetingNotesInput(notes_text="Test notes")
        input3 = MeetingNotesInput(notes_text="  Test   notes  ")
        
        # All should produce same hash after normalization
        assert input1.compute_hash() == input2.compute_hash()
        assert input2.compute_hash() == input3.compute_hash()


class TestEventDetails:
    """Tests for EventDetails model."""
    
    def test_basic_creation(self):
        """Test basic event creation."""
        event = EventDetails(title="Test Meeting")
        
        assert event.title == "Test Meeting"
        assert event.start_datetime is None
        assert event.attendees == []
        assert event.source_confidence == 0.0
    
    def test_is_complete(self):
        """Test completeness check."""
        # Incomplete - missing required fields
        event1 = EventDetails(title="Test")
        assert not event1.is_complete()
        
        # Complete - has all required fields
        now = datetime.now()
        event2 = EventDetails(
            title="Test",
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
        )
        assert event2.is_complete()
    
    def test_attendees_from_string(self):
        """Test attendees can be parsed from comma-separated string."""
        event = EventDetails(
            title="Test",
            attendees="alice@test.com, bob@test.com, carol@test.com"
        )
        
        assert len(event.attendees) == 3
        assert "alice@test.com" in event.attendees
    
    def test_dedupe_key(self):
        """Test deduplication key generation."""
        now = datetime.now()
        event1 = EventDetails(title="Meeting", start_datetime=now)
        event2 = EventDetails(title="Meeting", start_datetime=now)
        event3 = EventDetails(title="Different", start_datetime=now)
        
        assert event1.compute_dedupe_key() == event2.compute_dedupe_key()
        assert event1.compute_dedupe_key() != event3.compute_dedupe_key()


class TestStep:
    """Tests for Step model."""
    
    def test_basic_creation(self):
        """Test basic step creation."""
        step = Step(name="TestStep")
        
        assert step.name == "TestStep"
        assert step.status == StepStatus.PLANNED
        assert step.tool_name is None
        assert step.inputs == {}
    
    def test_with_tool(self):
        """Test step with tool configuration."""
        step = Step(
            name="CreateEvent",
            tool_name="create_calendar_event",
            inputs={"calendar_id": "primary"},
        )
        
        assert step.tool_name == "create_calendar_event"
        assert step.inputs["calendar_id"] == "primary"


class TestAgentState:
    """Tests for AgentState model."""
    
    def test_basic_creation(self):
        """Test basic state creation."""
        input_data = MeetingNotesInput(notes_text="Test")
        state = AgentState(input=input_data)
        
        assert state.input.notes_text == "Test"
        assert state.run_id is not None
        assert len(state.steps) == 0
        assert state.current_step_index == 0
    
    def test_get_current_step(self):
        """Test getting current step."""
        input_data = MeetingNotesInput(notes_text="Test")
        state = AgentState(input=input_data)
        
        # No steps
        assert state.get_current_step() is None
        
        # Add steps
        state.steps = [
            Step(name="Step1"),
            Step(name="Step2"),
        ]
        
        assert state.get_current_step().name == "Step1"
        state.current_step_index = 1
        assert state.get_current_step().name == "Step2"
    
    def test_mark_step_done(self):
        """Test marking step as done."""
        input_data = MeetingNotesInput(notes_text="Test")
        state = AgentState(input=input_data)
        state.steps = [Step(name="Step1"), Step(name="Step2")]
        
        state.mark_current_step_done({"result": "success"})
        
        assert state.steps[0].status == StepStatus.DONE
        assert state.steps[0].result == {"result": "success"}
        assert state.current_step_index == 1
    
    def test_mark_step_failed(self):
        """Test marking step as failed."""
        input_data = MeetingNotesInput(notes_text="Test")
        state = AgentState(input=input_data)
        state.steps = [Step(name="Step1")]
        
        state.mark_current_step_failed("Test error")
        
        assert state.steps[0].status == StepStatus.FAILED
        assert state.steps[0].error == "Test error"
        assert len(state.errors) == 1
    
    def test_all_steps_done(self):
        """Test checking if all steps are done."""
        input_data = MeetingNotesInput(notes_text="Test")
        state = AgentState(input=input_data)
        state.steps = [
            Step(name="Step1", status=StepStatus.DONE),
            Step(name="Step2", status=StepStatus.PLANNED),
        ]
        
        assert not state.all_steps_done()
        
        state.steps[1].status = StepStatus.DONE
        assert state.all_steps_done()
        
        # Skipped also counts as done
        state.steps[1].status = StepStatus.SKIPPED
        assert state.all_steps_done()


class TestGuardrailResult:
    """Tests for GuardrailResult model."""
    
    def test_default_values(self):
        """Test default guardrail result."""
        result = GuardrailResult()
        
        assert result.allow is False
        assert result.reasons == []
        assert result.required_questions == []
        assert result.duplicate_risk is False
    
    def test_with_issues(self):
        """Test guardrail with issues."""
        result = GuardrailResult(
            allow=False,
            reasons=["Missing title", "Low confidence"],
            required_questions=["What is the meeting title?"],
        )
        
        assert len(result.reasons) == 2
        assert len(result.required_questions) == 1


class TestFinalAnswer:
    """Tests for FinalAnswer model."""
    
    def test_basic_success(self):
        """Test successful final answer."""
        answer = FinalAnswer(
            success=True,
            summary="Meeting summary",
            decisions=["Decision 1"],
            action_items=[{"task": "Task 1", "owner": "Alice", "due": "Jan 20"}],
        )
        
        assert answer.success is True
        assert answer.run_id is not None
        assert len(answer.decisions) == 1
        assert len(answer.action_items) == 1
    
    def test_with_event(self):
        """Test final answer with calendar event."""
        event = EventDetails(title="Test Meeting")
        calendar_result = CalendarEventResult(
            success=True,
            event_id="abc123",
            html_link="https://calendar.google.com/event?eid=abc123",
        )
        
        answer = FinalAnswer(
            success=True,
            event_details=event,
            calendar_event_result=calendar_result,
        )
        
        assert answer.event_details.title == "Test Meeting"
        assert answer.calendar_event_result.event_id == "abc123"
    
    def test_with_questions(self):
        """Test final answer with questions for user."""
        answer = FinalAnswer(
            success=False,
            questions_for_user=["What time?", "Who should attend?"],
            missing_info=["Start time", "Attendees"],
        )
        
        assert not answer.success
        assert len(answer.questions_for_user) == 2
        assert len(answer.missing_info) == 2
