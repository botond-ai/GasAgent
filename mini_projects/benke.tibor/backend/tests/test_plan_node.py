"""
Unit tests for Plan Node functionality.
Tests ExecutionPlan generation, validation, and error handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from domain.llm_outputs import ExecutionPlan, ToolStep
from services.agent import QueryAgent, AgentState
from langchain_core.messages import HumanMessage


class TestExecutionPlanModel:
    """Tests for ExecutionPlan Pydantic model."""
    
    def test_valid_execution_plan(self):
        """Test valid ExecutionPlan creation."""
        plan = ExecutionPlan(
            reasoning="Need to search for information then compile results",
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search knowledge base",
                    arguments={"query": "test"},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.5,
            estimated_time_ms=1000
        )
        assert len(plan.steps) == 1
        assert plan.steps[0].step_id == 1
        assert plan.estimated_cost == 0.5
        assert plan.estimated_time_ms == 1000
    
    def test_multiple_steps_with_dependencies(self):
        """Test plan with multiple dependent steps."""
        plan = ExecutionPlan(
            reasoning="Search first, then process results",
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search knowledge base",
                    arguments={"query": "test"},
                    depends_on=[],
                    required=True
                ),
                ToolStep(
                    step_id=2,
                    tool_name="calculator",
                    description="Calculate summary",
                    arguments={"operation": "sum"},
                    depends_on=[1],  # Depends on step 1
                    required=True
                )
            ],
            estimated_cost=0.7,
            estimated_time_ms=2500
        )
        assert len(plan.steps) == 2
        assert plan.steps[1].depends_on == [1]
        assert plan.estimated_time_ms == 2500
    
    def test_max_five_steps_enforcement(self):
        """Test that max 5 steps is enforced."""
        # Valid: exactly 5 steps
        plan = ExecutionPlan(
            reasoning="Five-step process",
            steps=[
                ToolStep(
                    step_id=i,
                    tool_name="rag_search",
                    description=f"Step {i}",
                    arguments={},
                    depends_on=[],
                    required=True
                )
                for i in range(1, 6)  # 1-5
            ],
            estimated_cost=0.9,
            estimated_time_ms=5000
        )
        assert len(plan.steps) == 5
        
        # Invalid: 6 steps
        with pytest.raises(ValidationError) as exc_info:
            ExecutionPlan(
                reasoning="Six-step process (too many)",
                steps=[
                    ToolStep(
                        step_id=i,
                        tool_name="rag_search",
                        description=f"Step {i}",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                    for i in range(1, 7)  # 1-6
                ],
                estimated_cost=0.9,
                estimated_time_ms=5000
            )
        assert "at most 5 items" in str(exc_info.value).lower()
    
    def test_step_id_range_validation(self):
        """Test that step_id must be between 1 and 10."""
        # Valid: step_id=1
        step = ToolStep(
            step_id=1,
            tool_name="rag_search",
            description="Search",
            arguments={},
            depends_on=[],
            required=True
        )
        assert step.step_id == 1
        
        # Valid: step_id=10
        step = ToolStep(
            step_id=10,
            tool_name="rag_search",
            description="Search",
            arguments={},
            depends_on=[],
            required=True
        )
        assert step.step_id == 10
        
        # Invalid: step_id=0
        with pytest.raises(ValidationError):
            ToolStep(
                step_id=0,
                tool_name="rag_search",
                description="Search",
                arguments={},
                depends_on=[],
                required=True
            )
        
        # Invalid: step_id=11
        with pytest.raises(ValidationError):
            ToolStep(
                step_id=11,
                tool_name="rag_search",
                description="Search",
                arguments={},
                depends_on=[],
                required=True
            )
    
    def test_reasoning_length_validation(self):
        """Test reasoning must be 10-1000 characters."""
        # Valid: exactly 10 chars
        plan = ExecutionPlan(
            reasoning="1234567890",
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search",
                    arguments={},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.5,
            estimated_time_ms=1000
        )
        assert len(plan.reasoning) == 10
        
        # Valid: exactly 1000 chars
        plan = ExecutionPlan(
            reasoning="a" * 1000,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search",
                    arguments={},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.5,
            estimated_time_ms=1000
        )
        assert len(plan.reasoning) == 1000
        
        # Invalid: too short (9 chars)
        with pytest.raises(ValidationError):
            ExecutionPlan(
                reasoning="123456789",
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                ],
                estimated_cost=0.5,
                estimated_time_ms=1000
            )
        
        # Invalid: too long (1001 chars)
        with pytest.raises(ValidationError):
            ExecutionPlan(
                reasoning="a" * 1001,
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                ],
                estimated_cost=0.5,
                estimated_time_ms=1000
            )
    
    def test_cost_bounds_validation(self):
        """Test estimated_cost must be 0-1."""
        # Valid: exactly 0
        plan = ExecutionPlan(
            reasoning="Free operation" + "x" * 10,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search",
                    arguments={},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.0,
            estimated_time_ms=1000
        )
        assert plan.estimated_cost == 0.0
        
        # Valid: exactly 1
        plan = ExecutionPlan(
            reasoning="Expensive operation" + "x" * 10,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search",
                    arguments={},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=1.0,
            estimated_time_ms=1000
        )
        assert plan.estimated_cost == 1.0
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            ExecutionPlan(
                reasoning="Negative cost" + "x" * 10,
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                ],
                estimated_cost=-0.1,
                estimated_time_ms=1000
            )
        
        # Invalid: > 1
        with pytest.raises(ValidationError):
            ExecutionPlan(
                reasoning="Over cost limit" + "x" * 10,
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                ],
                estimated_cost=1.1,
                estimated_time_ms=1000
            )
    
    def test_time_bounds_validation(self):
        """Test estimated_time_ms must be 100-120000."""
        # Valid: exactly 100ms
        plan = ExecutionPlan(
            reasoning="Fast operation" + "x" * 10,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search",
                    arguments={},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.5,
            estimated_time_ms=100
        )
        assert plan.estimated_time_ms == 100
        
        # Valid: exactly 120000ms
        plan = ExecutionPlan(
            reasoning="Slow operation" + "x" * 20,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search",
                    arguments={},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.8,
            estimated_time_ms=120000
        )
        assert plan.estimated_time_ms == 120000
        
        # Invalid: too fast (99ms)
        with pytest.raises(ValidationError):
            ExecutionPlan(
                reasoning="Too fast operation" + "x" * 10,
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                ],
                estimated_cost=0.1,
                estimated_time_ms=99
            )
        
        # Invalid: too slow (120001ms)
        with pytest.raises(ValidationError):
            ExecutionPlan(
                reasoning="Too slow operation" + "x" * 10,
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    )
                ],
                estimated_cost=0.9,
                estimated_time_ms=120001
            )
    
    def test_dependency_validation_invalid_reference(self):
        """Test that dependencies must reference existing steps."""
        # Invalid: step 2 depends on non-existent step 5
        with pytest.raises(ValidationError) as exc_info:
            ExecutionPlan(
                reasoning="Invalid dependency reference" + "x" * 10,
                steps=[
                    ToolStep(
                        step_id=1,
                        tool_name="rag_search",
                        description="Search",
                        arguments={},
                        depends_on=[],
                        required=True
                    ),
                    ToolStep(
                        step_id=2,
                        tool_name="calculator",
                        description="Calculate",
                        arguments={},
                        depends_on=[5],  # Step 5 doesn't exist!
                        required=True
                    )
                ],
                estimated_cost=0.5,
                estimated_time_ms=2000
            )
        # Check that error message mentions the dependency issue
        assert "non-existent" in str(exc_info.value).lower() or "depends" in str(exc_info.value).lower()
    
    def test_tool_name_validation(self):
        """Test tool_name field constraints."""
        # Valid: standard tool
        step = ToolStep(
            step_id=1,
            tool_name="rag_search",
            description="Search knowledge base",
            arguments={},
            depends_on=[],
            required=True
        )
        assert step.tool_name == "rag_search"
        
        # Invalid: empty tool name
        with pytest.raises(ValidationError):
            ToolStep(
                step_id=1,
                tool_name="",
                description="Search",
                arguments={},
                depends_on=[],
                required=True
            )


class TestPlanNodeAsync:
    """Tests for async _plan_node method."""
    
    @pytest.mark.asyncio
    async def test_plan_node_success(self):
        """Test successful plan generation."""
        # Mock LLM client
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        
        plan = ExecutionPlan(
            reasoning="Generate a comprehensive answer" + "x" * 10,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search for information",
                    arguments={"query": "test query"},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.5,
            estimated_time_ms=1500
        )
        
        mock_structured_llm.ainvoke = AsyncMock(return_value=plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "What is the capital of France?",
            "domain": "general",
            "messages": [],
            "memory_summary": "User is learning geography"
        }
        
        result = await agent._plan_node(state)
        
        # Verify execution_plan was set
        assert result.get("execution_plan") is not None
        plan_dict = result["execution_plan"]
        assert plan_dict["estimated_time_ms"] == 1500
        assert len(plan_dict["steps"]) == 1
        assert plan_dict["steps"][0]["tool_name"] == "rag_search"
    
    @pytest.mark.asyncio
    async def test_plan_node_error_handling_non_blocking(self):
        """Test that plan node errors are non-blocking."""
        # Mock LLM to raise exception
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM API error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "Test query",
            "domain": "it",
            "messages": [],
        }
        
        result = await agent._plan_node(state)
        
        # Verify execution_plan is None (not set due to error)
        assert result.get("execution_plan") is None
        
        # Verify state is still returned (non-blocking)
        assert result["query"] == "Test query"
        assert result["domain"] == "it"
    
    @pytest.mark.asyncio
    async def test_plan_node_with_memory_context(self):
        """Test plan node uses memory context."""
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        
        plan = ExecutionPlan(
            reasoning="Use previous knowledge" + "x" * 20,
            steps=[
                ToolStep(
                    step_id=1,
                    tool_name="rag_search",
                    description="Search with context",
                    arguments={"query": "related to previous topic"},
                    depends_on=[],
                    required=True
                )
            ],
            estimated_cost=0.3,
            estimated_time_ms=800
        )
        
        mock_structured_llm.ainvoke = AsyncMock(return_value=plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "Continue with next question",
            "domain": "finance",
            "messages": [],
            "memory_summary": "User discussing budget planning for 2024"
        }
        
        result = await agent._plan_node(state)
        
        # Verify plan was generated
        assert result.get("execution_plan") is not None
        
        # Verify the LLM was called (proving memory context was passed)
        mock_structured_llm.ainvoke.assert_called_once()
        call_args = mock_structured_llm.ainvoke.call_args[0][0]
        assert isinstance(call_args, list)
        assert any("budget planning" in str(arg) for arg in call_args)


@pytest.mark.asyncio
async def test_plan_node_integration_with_agent_state():
    """Integration test: plan node updates AgentState correctly."""
    mock_llm = MagicMock()
    mock_structured_llm = AsyncMock()
    
    plan = ExecutionPlan(
        reasoning="Comprehensive analysis plan" + "x" * 20,
        steps=[
            ToolStep(
                step_id=1,
                tool_name="rag_search",
                description="Retrieve documents",
                arguments={"query": "analysis"},
                depends_on=[],
                required=True
            ),
            ToolStep(
                step_id=2,
                tool_name="calculator",
                description="Process results",
                arguments={"operation": "aggregate"},
                depends_on=[1],
                required=False
            )
        ],
        estimated_cost=0.6,
        estimated_time_ms=3000
    )
    
    mock_structured_llm.ainvoke = AsyncMock(return_value=plan)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
    
    agent = QueryAgent(llm_client=mock_llm, rag_client=None)
    
    initial_state: AgentState = {
        "query": "Analyze the data",
        "domain": "finance",
        "messages": [HumanMessage(content="Analyze the data")],
        "memory_facts": ["Previous analysis showed X", "User prefers detailed reports"]
    }
    
    result = await agent._plan_node(initial_state)
    
    # Verify state preserved original fields
    assert result["query"] == "Analyze the data"
    assert result["domain"] == "finance"
    assert len(result["messages"]) > 0
    
    # Verify execution_plan added
    assert result.get("execution_plan") is not None
    plan_data = result["execution_plan"]
    assert len(plan_data["steps"]) == 2
    assert plan_data["steps"][1]["depends_on"] == [1]
    assert plan_data["estimated_time_ms"] == 3000
