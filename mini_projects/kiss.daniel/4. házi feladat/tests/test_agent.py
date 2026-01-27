"""
Integration tests for the agent graph.
Uses mock LLM and calendar for testing workflow.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.agent.state import (
    AgentState,
    MeetingNotesInput,
    EventDetails,
    Step,
    StepStatus,
    SummarizerOutput,
    ExtractorOutput,
)
from app.agent.nodes import NodeExecutor, create_node_executor
from app.llm.ollama_client import OllamaClient
from app.memory.store import InMemoryStore
from app.tools.google_calendar import MockGoogleCalendarTool
from tests.fixtures import SAMPLE_NOTES_CLEAR, SAMPLE_NOTES_AMBIGUOUS


class TestNodeExecutor:
    """Tests for NodeExecutor."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM client."""
        mock = Mock(spec=OllamaClient)
        mock.validate_model.return_value = (True, None)
        return mock
    
    @pytest.fixture
    def executor(self, mock_llm):
        """Create a node executor with mocks."""
        return NodeExecutor(
            llm_client=mock_llm,
            memory_store=InMemoryStore(),
            calendar_tool=MockGoogleCalendarTool(),
        )
    
    @pytest.fixture
    def basic_state(self):
        """Create a basic agent state for testing."""
        input_data = MeetingNotesInput(notes_text="Test meeting notes")
        return AgentState(input=input_data)
    
    def test_planner_creates_steps(self, executor, basic_state, mock_llm):
        """Test that planner creates execution steps."""
        # Mock LLM response
        from app.agent.state import PlannerOutput
        mock_llm.generate_structured.return_value = PlannerOutput(
            steps=[
                Step(name="SummarizeNotes"),
                Step(name="ExtractNextMeetingDetails"),
                Step(name="ComposeFinalAnswer"),
            ],
            rationale="Test plan",
        )
        
        result = executor.planner_node(basic_state)
        
        assert len(result.steps) == 3
        assert result.current_step_index == 0
        assert result.steps[0].name == "SummarizeNotes"
    
    def test_planner_fallback_on_error(self, executor, basic_state, mock_llm):
        """Test that planner uses default steps on LLM error."""
        from app.llm.ollama_client import OllamaError
        mock_llm.generate_structured.side_effect = OllamaError("Test error")
        
        result = executor.planner_node(basic_state)
        
        # Should have default steps
        assert len(result.steps) > 0
        assert any(s.name == "SummarizeNotes" for s in result.steps)
        assert len(result.warnings) > 0
    
    def test_summarizer_extracts_info(self, executor, basic_state, mock_llm):
        """Test that summarizer extracts meeting info."""
        basic_state.steps = [Step(name="SummarizeNotes")]
        
        mock_llm.generate_structured.return_value = SummarizerOutput(
            summary="Test summary of the meeting",
            decisions=["Decision 1", "Decision 2"],
            action_items=[{"task": "Task 1", "owner": "Alice", "due": "Jan 20"}],
            risks_open_questions=["Risk 1"],
            next_meeting_hint="Next Tuesday",
        )
        
        result = executor.summarizer_node(basic_state)
        
        assert result.summary == "Test summary of the meeting"
        assert len(result.decisions) == 2
        assert len(result.action_items) == 1
        assert result.steps[0].status == StepStatus.DONE
    
    def test_extractor_extracts_event(self, executor, basic_state, mock_llm):
        """Test that extractor extracts event details."""
        basic_state.steps = [Step(name="ExtractNextMeetingDetails")]
        
        mock_llm.generate_structured.return_value = ExtractorOutput(
            title="Sprint Planning",
            date="2026-01-20",
            time="10:00",
            duration_minutes=60,
            timezone="Europe/Budapest",
            location="Room A",
            attendees=["alice@test.com"],
            confidence=0.9,
            warnings=[],
        )
        
        result = executor.extractor_node(basic_state)
        
        assert result.event_details is not None
        assert result.event_details.title == "Sprint Planning"
        assert result.event_details.source_confidence == 0.9
    
    def test_validator_adds_defaults(self, executor, basic_state):
        """Test that validator adds default values."""
        basic_state.steps = [Step(name="ValidateAndNormalizeEventDetails")]
        basic_state.event_details = EventDetails(
            title="Test Meeting",
            start_datetime=datetime.now(),
            # No end_datetime - should be defaulted
        )
        
        result = executor.validator_node(basic_state)
        
        assert result.event_details.end_datetime is not None
        assert "defaulting to 30 minutes" in str(result.event_details.extraction_warnings).lower()
    
    def test_guardrail_blocks_incomplete(self, executor, basic_state):
        """Test that guardrail blocks incomplete events."""
        basic_state.steps = [Step(name="GuardrailCheck")]
        basic_state.event_details = EventDetails(
            title="",  # Missing title
            source_confidence=0.3,  # Low confidence
        )
        
        result = executor.guardrail_node(basic_state)
        
        assert result.guardrail_result is not None
        assert result.guardrail_result.allow is False
        assert len(result.guardrail_result.reasons) > 0
    
    def test_guardrail_allows_complete(self, executor, basic_state):
        """Test that guardrail allows complete events."""
        basic_state.steps = [Step(name="GuardrailCheck")]
        basic_state.event_details = EventDetails(
            title="Complete Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
            source_confidence=0.9,
        )
        
        result = executor.guardrail_node(basic_state)
        
        assert result.guardrail_result.allow is True
    
    def test_guardrail_blocks_dry_run(self, executor):
        """Test that guardrail blocks in dry run mode."""
        input_data = MeetingNotesInput(notes_text="Test", dry_run=True)
        state = AgentState(input=input_data)
        state.steps = [Step(name="GuardrailCheck")]
        state.event_details = EventDetails(
            title="Complete Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
            source_confidence=0.9,
        )
        
        result = executor.guardrail_node(state)
        
        assert result.guardrail_result.allow is False
        assert "dry run" in str(result.guardrail_result.reasons).lower()
    
    def test_tool_node_creates_event(self, executor, basic_state):
        """Test that tool node creates calendar event."""
        basic_state.steps = [Step(name="CreateGoogleCalendarEvent", tool_name="create_calendar_event")]
        basic_state.guardrail_result = Mock(allow=True)
        basic_state.event_details = EventDetails(
            title="Test Event",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
        )
        
        result = executor.tool_node(basic_state)
        
        assert result.calendar_event_result is not None
        assert result.calendar_event_result.success is True
        assert result.calendar_event_result.event_id is not None
    
    def test_tool_node_skips_on_guardrail_block(self, executor, basic_state):
        """Test that tool node skips when guardrail blocks."""
        basic_state.steps = [Step(name="CreateGoogleCalendarEvent")]
        basic_state.guardrail_result = Mock(allow=False)
        
        result = executor.tool_node(basic_state)
        
        assert result.steps[0].status == StepStatus.SKIPPED
    
    def test_final_answer_composes_result(self, executor, basic_state):
        """Test that final answer composes result."""
        basic_state.steps = [Step(name="ComposeFinalAnswer")]
        basic_state.summary = "Test summary"
        basic_state.decisions = ["Decision 1"]
        basic_state.event_details = EventDetails(title="Test Event")
        
        result = executor.final_answer_node(basic_state)
        
        assert result.final_answer is not None
        assert result.final_answer.summary == "Test summary"
        assert result.is_complete is True
    
    def test_router_routes_correctly(self, executor, basic_state):
        """Test that router routes to correct nodes."""
        basic_state.steps = [
            Step(name="SummarizeNotes"),
            Step(name="ExtractNextMeetingDetails"),
            Step(name="ComposeFinalAnswer"),
        ]
        
        # First step
        basic_state.current_step_index = 0
        assert executor.router_node(basic_state) == "summarizer"
        
        # Second step
        basic_state.current_step_index = 1
        assert executor.router_node(basic_state) == "extractor"
        
        # Final step
        basic_state.current_step_index = 2
        assert executor.router_node(basic_state) == "final_answer"
    
    def test_should_continue_logic(self, executor, basic_state):
        """Test should_continue decision logic."""
        basic_state.steps = [Step(name="Step1")]
        
        # Should continue - not complete
        assert executor.should_continue(basic_state) == "continue"
        
        # Should end - marked complete
        basic_state.is_complete = True
        assert executor.should_continue(basic_state) == "end"
        
        # Should end - all steps done
        basic_state.is_complete = False
        basic_state.steps[0].status = StepStatus.DONE
        basic_state.current_step_index = 1
        assert executor.should_continue(basic_state) == "end"


class TestGuardrailSensitiveContent:
    """Tests for guardrail sensitive content detection."""
    
    @pytest.fixture
    def executor(self):
        return NodeExecutor(
            llm_client=Mock(),
            memory_store=InMemoryStore(),
            calendar_tool=MockGoogleCalendarTool(),
        )
    
    def test_detects_password_in_description(self, executor):
        """Test detection of password in description."""
        state = AgentState(input=MeetingNotesInput(notes_text="Test"))
        state.steps = [Step(name="GuardrailCheck")]
        state.event_details = EventDetails(
            title="Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
            description="Login credentials: password: secret123",
            source_confidence=0.9,
        )
        
        result = executor.guardrail_node(state)
        
        assert result.guardrail_result.allow is False
        assert "sensitive" in str(result.guardrail_result.reasons).lower()
    
    def test_detects_api_key(self, executor):
        """Test detection of API key in description."""
        state = AgentState(input=MeetingNotesInput(notes_text="Test"))
        state.steps = [Step(name="GuardrailCheck")]
        state.event_details = EventDetails(
            title="Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
            description="Use api_key: sk-12345 for access",
            source_confidence=0.9,
        )
        
        result = executor.guardrail_node(state)
        
        assert result.guardrail_result.allow is False
