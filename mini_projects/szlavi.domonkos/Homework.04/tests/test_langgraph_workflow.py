"""Tests for LangGraph workflow.

Tests the multi-step agent orchestration including plan generation,
tool routing, execution, and summary generation.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.langgraph_workflow import (
    MeetingAssistantWorkflow,
    WorkflowState,
    ExecutionStep,
    ToolType,
)


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    api_key = "test-key"
    vector_store = MagicMock()
    rag_agent = MagicMock()
    calendar_service = MagicMock()
    geolocation_client = MagicMock()
    
    return {
        "api_key": api_key,
        "vector_store": vector_store,
        "rag_agent": rag_agent,
        "calendar_service": calendar_service,
        "geolocation_client": geolocation_client,
    }


@pytest.fixture
def workflow(mock_services):
    """Create a workflow instance with mock services."""
    return MeetingAssistantWorkflow(
        api_key=mock_services["api_key"],
        vector_store=mock_services["vector_store"],
        rag_agent=mock_services["rag_agent"],
        google_calendar_service=mock_services["calendar_service"],
        geolocation_client=mock_services["geolocation_client"],
    )


class TestExecutionStep:
    """Test ExecutionStep dataclass."""

    def test_execution_step_creation(self):
        """Test creating an execution step."""
        step = ExecutionStep(
            step_id=1,
            action="Test action",
            tool=ToolType.RAG_SEARCH,
            parameters={"query": "test"},
        )
        assert step.step_id == 1
        assert step.action == "Test action"
        assert step.tool == ToolType.RAG_SEARCH
        assert step.status == "pending"

    def test_execution_step_with_result(self):
        """Test execution step with result."""
        step = ExecutionStep(
            step_id=1,
            action="Search",
            tool=ToolType.RAG_SEARCH,
            parameters={},
            result={"documents": ["doc1", "doc2"]},
            status="completed",
        )
        assert step.result == {"documents": ["doc1", "doc2"]}
        assert step.status == "completed"


class TestWorkflowState:
    """Test WorkflowState dataclass."""

    def test_workflow_state_creation(self):
        """Test creating a workflow state."""
        state = WorkflowState(user_input="Test request")
        assert state.user_input == "Test request"
        assert state.execution_plan == []
        assert state.current_step_index == 0
        assert state.executed_steps == []

    def test_workflow_state_with_steps(self):
        """Test workflow state with execution steps."""
        step1 = ExecutionStep(1, "Action 1", ToolType.RAG_SEARCH, {})
        step2 = ExecutionStep(2, "Action 2", ToolType.GOOGLE_CALENDAR, {})
        
        state = WorkflowState(
            user_input="Test",
            execution_plan=[step1, step2],
        )
        assert len(state.execution_plan) == 2
        assert state.execution_plan[0].step_id == 1


class TestPlanGeneration:
    """Test plan node functionality."""

    @patch('app.langgraph_workflow.openai.ChatCompletion.create')
    def test_plan_node_generates_steps(self, mock_llm, workflow, mock_services):
        """Test that plan node generates execution steps."""
        # Mock LLM response
        mock_llm.return_value.choices[0].message.content = """{
            "execution_plan": [
                {
                    "step_id": 1,
                    "action": "Search documents",
                    "required_tool": "rag_search",
                    "parameters": {"query": "test"}
                }
            ]
        }"""
        
        # Mock vector store search
        mock_services["vector_store"].search.return_value = [
            ("doc1", 0.95, "Test document"),
        ]
        
        state = WorkflowState(user_input="Find test documents")
        result = workflow.plan_node(state)
        
        assert len(result.execution_plan) > 0
        assert result.execution_plan[0].tool == ToolType.RAG_SEARCH


class TestToolRouter:
    """Test tool router functionality."""

    def test_tool_router_calendar(self, workflow):
        """Test tool router identifies calendar commands."""
        step = ExecutionStep(1, "Show calendar events", ToolType.NONE, {})
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.tool_router(state)
        assert result.execution_plan[0].tool == ToolType.GOOGLE_CALENDAR

    def test_tool_router_geolocation(self, workflow):
        """Test tool router identifies geolocation commands."""
        step = ExecutionStep(1, "Look up IP location", ToolType.NONE, {})
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.tool_router(state)
        assert result.execution_plan[0].tool == ToolType.IP_GEOLOCATION

    def test_tool_router_rag_search(self, workflow):
        """Test tool router identifies search commands."""
        step = ExecutionStep(1, "Search for documents", ToolType.NONE, {})
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.tool_router(state)
        assert result.execution_plan[0].tool == ToolType.RAG_SEARCH


class TestActionExecution:
    """Test action node functionality."""

    def test_action_node_rag_search(self, workflow, mock_services):
        """Test action node executes RAG search."""
        mock_services["vector_store"].search.return_value = [
            ("doc1", 0.95, "Test result"),
        ]
        
        step = ExecutionStep(
            1,
            "Search",
            ToolType.RAG_SEARCH,
            {"query": "test"},
        )
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.action_node(state)
        assert result.execution_plan[0].status == "completed"
        assert result.execution_plan[0].result is not None

    def test_action_node_calendar(self, workflow, mock_services):
        """Test action node executes calendar action."""
        mock_services["calendar_service"].get_upcoming_events.return_value = [
            {"title": "Meeting", "start": "2026-01-20T10:00:00Z"},
        ]
        
        step = ExecutionStep(
            1,
            "Get calendar events",
            ToolType.GOOGLE_CALENDAR,
            {"action_type": "list_events"},
        )
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.action_node(state)
        assert result.execution_plan[0].status == "completed"

    def test_action_node_geolocation(self, workflow, mock_services):
        """Test action node executes geolocation action."""
        mock_services["geolocation_client"].get_location_from_ip.return_value = {
            "country": "US",
            "city": "Mountain View",
        }
        
        step = ExecutionStep(
            1,
            "Look up IP",
            ToolType.IP_GEOLOCATION,
            {"ip": "8.8.8.8"},
        )
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.action_node(state)
        assert result.execution_plan[0].status == "completed"


class TestObservationNode:
    """Test observation node functionality."""

    def test_observation_node_updates_state(self, workflow):
        """Test observation node updates workflow state."""
        step = ExecutionStep(
            1,
            "Action",
            ToolType.RAG_SEARCH,
            {},
            result={"data": "test"},
            status="completed",
        )
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=0,
        )
        
        result = workflow.observation_node(state)
        assert result.current_step_index == 1
        assert len(result.executed_steps) == 1
        assert len(result.observations) > 0


class TestExecutorLoop:
    """Test executor loop functionality."""

    def test_executor_loop_should_continue(self, workflow):
        """Test executor loop decides to continue."""
        step1 = ExecutionStep(1, "Action 1", ToolType.RAG_SEARCH, {})
        step2 = ExecutionStep(2, "Action 2", ToolType.GOOGLE_CALENDAR, {})
        
        state = WorkflowState(
            user_input="test",
            execution_plan=[step1, step2],
            current_step_index=0,
        )
        
        decision = workflow._should_continue_execution(state)
        assert decision == "continue"

    def test_executor_loop_should_finish(self, workflow):
        """Test executor loop decides to finish."""
        step = ExecutionStep(1, "Action", ToolType.RAG_SEARCH, {})
        
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            current_step_index=1,
        )
        
        decision = workflow._should_continue_execution(state)
        assert decision == "done"


class TestSummaryGeneration:
    """Test summary node functionality."""

    @patch('app.langgraph_workflow.openai.ChatCompletion.create')
    def test_summary_node_generates_summary(self, mock_llm, workflow):
        """Test summary node generates a meeting summary."""
        mock_llm.return_value.choices[0].message.content = "Test summary"
        
        step = ExecutionStep(1, "Search", ToolType.RAG_SEARCH, {}, status="completed")
        state = WorkflowState(
            user_input="test",
            execution_plan=[step],
            executed_steps=[step],
        )
        
        result = workflow.summary_node(state)
        assert result.meeting_summary == "Test summary"


class TestFinalAnswerGeneration:
    """Test final answer node functionality."""

    def test_final_answer_node_creates_report(self, workflow):
        """Test final answer node creates comprehensive report."""
        step = ExecutionStep(1, "Test action", ToolType.RAG_SEARCH, {}, status="completed")
        state = WorkflowState(
            user_input="Test request",
            execution_plan=[step],
            executed_steps=[step],
            meeting_summary="Test summary",
        )
        
        result = workflow.final_answer_node(state)
        assert result.final_answer is not None
        assert "Test request" in result.final_answer
        assert "Test summary" in result.final_answer


class TestPlanParsing:
    """Test execution plan parsing."""

    def test_parse_valid_execution_plan(self, workflow):
        """Test parsing valid execution plan JSON."""
        plan_text = """{
            "execution_plan": [
                {
                    "step_id": 1,
                    "action": "Search documents",
                    "required_tool": "rag_search",
                    "parameters": {"query": "test"}
                },
                {
                    "step_id": 2,
                    "action": "Check calendar",
                    "required_tool": "google_calendar",
                    "parameters": {"action_type": "list_events"}
                }
            ]
        }"""
        
        steps = workflow._parse_execution_plan(plan_text)
        assert len(steps) == 2
        assert steps[0].tool == ToolType.RAG_SEARCH
        assert steps[1].tool == ToolType.GOOGLE_CALENDAR

    def test_parse_malformed_plan_returns_default(self, workflow):
        """Test parsing malformed plan returns default step."""
        plan_text = "This is not valid JSON"
        
        steps = workflow._parse_execution_plan(plan_text)
        assert len(steps) == 1
        assert steps[0].action == "Default search action"


class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""

    @patch('app.langgraph_workflow.openai.ChatCompletion.create')
    def test_workflow_run_end_to_end(self, mock_llm, workflow, mock_services):
        """Test complete workflow execution."""
        # Mock LLM responses
        mock_llm.side_effect = [
            # Plan generation response
            MagicMock(choices=[MagicMock(message=MagicMock(content="""{
                "execution_plan": [
                    {
                        "step_id": 1,
                        "action": "Search documents",
                        "required_tool": "rag_search",
                        "parameters": {"query": "test"}
                    }
                ]
            }"""))]),
            # Summary generation response
            MagicMock(choices=[MagicMock(message=MagicMock(content="Generated summary"))]),
        ]
        
        # Mock vector store
        mock_services["vector_store"].search.return_value = [
            ("doc1", 0.95, "Test document"),
        ]
        
        result = workflow.run("Test user request")
        
        assert result['user_input'] == "Test user request"
        assert result['executed_steps'] >= 0
        assert result['final_answer'] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
