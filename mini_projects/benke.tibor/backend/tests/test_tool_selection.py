"""
Unit tests for Tool Selection Node functionality.
Tests ToolSelection, routing logic, and tool availability.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from domain.llm_outputs import ToolSelection, ToolCall
from services.agent import QueryAgent, AgentState


class TestToolSelectionModel:
    """Tests for ToolSelection and ToolCall Pydantic models."""
    
    def test_valid_tool_call(self):
        """Test valid ToolCall creation."""
        tool_call = ToolCall(
            tool_name="rag_search",
            arguments={"query": "test", "domain": "it"},
            confidence=0.9,
            reasoning="Need to search knowledge base"
        )
        assert tool_call.tool_name == "rag_search"
        assert tool_call.confidence == 0.9
        assert "query" in tool_call.arguments
    
    def test_tool_call_confidence_warning(self):
        """Test that low confidence triggers warning but doesn't fail."""
        tool_call = ToolCall(
            tool_name="jira_create",
            arguments={"summary": "test"},
            confidence=0.4,  # Below 0.5 threshold
            reasoning="Low confidence tool selection"
        )
        assert tool_call.confidence == 0.4  # Should still be valid
    
    def test_tool_call_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        # Valid: 0.0
        tool_call = ToolCall(
            tool_name="calculator",
            arguments={},
            confidence=0.0,
            reasoning="Zero confidence"
        )
        assert tool_call.confidence == 0.0
        
        # Valid: 1.0
        tool_call = ToolCall(
            tool_name="email_send",
            arguments={},
            confidence=1.0,
            reasoning="Full confidence"
        )
        assert tool_call.confidence == 1.0
        
        # Invalid: > 1.0
        with pytest.raises(ValidationError):
            ToolCall(
                tool_name="rag_search",
                arguments={},
                confidence=1.5,
                reasoning="Invalid confidence"
            )
    
    def test_valid_tool_selection_rag_only(self):
        """Test valid ToolSelection with RAG only."""
        selection = ToolSelection(
            reasoning="User asking for policy information, RAG search is sufficient",
            selected_tools=[
                ToolCall(
                    tool_name="rag_search",
                    arguments={"query": "vacation policy", "domain": "hr"},
                    confidence=0.95,
                    reasoning="HR policy query"
                )
            ],
            fallback_plan="If RAG unavailable, provide summary from memory",
            route="rag_only"
        )
        assert len(selection.selected_tools) == 1
        assert selection.route == "rag_only"
    
    def test_valid_tool_selection_tools_only(self):
        """Test valid ToolSelection with tools only (no RAG)."""
        selection = ToolSelection(
            reasoning="Need to create IT ticket, no knowledge base search needed",
            selected_tools=[
                ToolCall(
                    tool_name="jira_create",
                    arguments={"summary": "VPN not working", "description": "Can't connect"},
                    confidence=0.9,
                    reasoning="IT support request"
                )
            ],
            fallback_plan="If Jira unavailable, provide manual ticket creation instructions",
            route="tools_only"
        )
        assert len(selection.selected_tools) == 1
        assert selection.route == "tools_only"
    
    def test_valid_tool_selection_rag_and_tools(self):
        """Test valid ToolSelection with both RAG and tools."""
        selection = ToolSelection(
            reasoning="Need RAG context for ticket description, then create Jira ticket",
            selected_tools=[
                ToolCall(
                    tool_name="rag_search",
                    arguments={"query": "VPN setup", "domain": "it"},
                    confidence=0.85,
                    reasoning="Get VPN documentation"
                ),
                ToolCall(
                    tool_name="jira_create",
                    arguments={"summary": "VPN issue", "description": "..."},
                    confidence=0.8,
                    reasoning="Create support ticket"
                )
            ],
            fallback_plan="If tools fail, provide manual instructions",
            route="rag_and_tools"
        )
        assert len(selection.selected_tools) == 2
        assert selection.route == "rag_and_tools"
    
    def test_max_three_tools_enforcement(self):
        """Test that max 3 tools is enforced."""
        # Valid: exactly 3 tools
        selection = ToolSelection(
            reasoning="Complex query needs multiple tools",
            selected_tools=[
                ToolCall(
                    tool_name="rag_search",
                    arguments={"query": "test"},
                    confidence=0.8,
                    reasoning="Search docs"
                ),
                ToolCall(
                    tool_name="jira_create",
                    arguments={"summary": "test"},
                    confidence=0.7,
                    reasoning="Create ticket"
                ),
                ToolCall(
                    tool_name="email_send",
                    arguments={"to": "test@example.com"},
                    confidence=0.6,
                    reasoning="Send notification"
                )
            ],
            fallback_plan="Fallback to RAG only",
            route="rag_and_tools"
        )
        assert len(selection.selected_tools) == 3
        
        # Invalid: 4 tools
        with pytest.raises(ValidationError):
            ToolSelection(
                reasoning="Too many tools",
                selected_tools=[
                    ToolCall(tool_name="rag_search", arguments={}, confidence=0.8, reasoning="test"),
                    ToolCall(tool_name="jira_create", arguments={}, confidence=0.7, reasoning="test"),
                    ToolCall(tool_name="email_send", arguments={}, confidence=0.6, reasoning="test"),
                    ToolCall(tool_name="calculator", arguments={}, confidence=0.5, reasoning="test")
                ],
                fallback_plan="Fallback",
                route="tools_only"
            )
    
    def test_route_auto_correction(self):
        """Test that route is auto-corrected if inconsistent with tools."""
        # Declared rag_only but has both RAG and Jira → should auto-correct to rag_and_tools
        selection = ToolSelection(
            reasoning="Both RAG and tools needed",
            selected_tools=[
                ToolCall(tool_name="rag_search", arguments={}, confidence=0.9, reasoning="test reasoning"),
                ToolCall(tool_name="jira_create", arguments={}, confidence=0.8, reasoning="test reasoning")
            ],
            fallback_plan="Use default search",
            route="rag_only"  # Incorrect!
        )
        # Should auto-correct to rag_and_tools
        assert selection.route == "rag_and_tools"
        
        # Declared tools_only but only has RAG → should auto-correct to rag_only
        selection = ToolSelection(
            reasoning="RAG search is necessary for this query",
            selected_tools=[
                ToolCall(tool_name="rag_search", arguments={}, confidence=0.9, reasoning="test reasoning")
            ],
            fallback_plan="Use default search",
            route="tools_only"  # Incorrect!
        )
        # Should auto-correct to rag_only
        assert selection.route == "rag_only"


class TestToolSelectionNodeAsync:
    """Tests for async _tool_selection_node method."""
    
    @pytest.mark.asyncio
    async def test_tool_selection_node_rag_only(self):
        """Test tool selection returns RAG-only route."""
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        
        selection = ToolSelection(
            reasoning="Simple knowledge base query, RAG search sufficient",
            selected_tools=[
                ToolCall(
                    tool_name="rag_search",
                    arguments={"query": "vacation policy", "domain": "hr"},
                    confidence=0.95,
                    reasoning="HR policy search"
                )
            ],
            fallback_plan="If RAG fails, use memory summary",
            route="rag_only"
        )
        
        mock_structured_llm.ainvoke = AsyncMock(return_value=selection)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "What is the vacation policy?",
            "domain": "hr",
            "messages": []
        }
        
        result = await agent._tool_selection_node(state)
        
        # Verify tool_selection was set
        assert result.get("tool_selection") is not None
        tool_sel = result["tool_selection"]
        assert tool_sel["route"] == "rag_only"
        assert len(tool_sel["selected_tools"]) == 1
        assert tool_sel["selected_tools"][0]["tool_name"] == "rag_search"
    
    @pytest.mark.asyncio
    async def test_tool_selection_node_tools_only(self):
        """Test tool selection returns tools-only route."""
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        
        selection = ToolSelection(
            reasoning="Need to create IT ticket, no RAG needed",
            selected_tools=[
                ToolCall(
                    tool_name="jira_create",
                    arguments={"summary": "VPN issue", "description": "Can't connect"},
                    confidence=0.9,
                    reasoning="IT support ticket"
                )
            ],
            fallback_plan="Manual ticket instructions if Jira fails",
            route="tools_only"
        )
        
        mock_structured_llm.ainvoke = AsyncMock(return_value=selection)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "Create a ticket for VPN issue",
            "domain": "it",
            "messages": []
        }
        
        result = await agent._tool_selection_node(state)
        
        assert result.get("tool_selection") is not None
        tool_sel = result["tool_selection"]
        assert tool_sel["route"] == "tools_only"
        assert tool_sel["selected_tools"][0]["tool_name"] == "jira_create"
    
    @pytest.mark.asyncio
    async def test_tool_selection_node_rag_and_tools(self):
        """Test tool selection returns rag_and_tools route."""
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        
        selection = ToolSelection(
            reasoning="Need RAG for context, then create Jira ticket",
            selected_tools=[
                ToolCall(
                    tool_name="rag_search",
                    arguments={"query": "VPN setup", "domain": "it"},
                    confidence=0.85,
                    reasoning="Get VPN docs"
                ),
                ToolCall(
                    tool_name="jira_create",
                    arguments={"summary": "VPN", "description": "..."},
                    confidence=0.8,
                    reasoning="Create ticket"
                )
            ],
            fallback_plan="RAG-only fallback",
            route="rag_and_tools"
        )
        
        mock_structured_llm.ainvoke = AsyncMock(return_value=selection)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "Help with VPN and create ticket",
            "domain": "it",
            "messages": []
        }
        
        result = await agent._tool_selection_node(state)
        
        assert result.get("tool_selection") is not None
        tool_sel = result["tool_selection"]
        assert tool_sel["route"] == "rag_and_tools"
        assert len(tool_sel["selected_tools"]) == 2
    
    @pytest.mark.asyncio
    async def test_tool_selection_node_error_fallback(self):
        """Test tool selection falls back to rag_only on error."""
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM API error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "query": "Test query",
            "domain": "general",
            "messages": []
        }
        
        result = await agent._tool_selection_node(state)
        
        # Should fallback to rag_only
        assert result.get("tool_selection") is not None
        tool_sel = result["tool_selection"]
        assert tool_sel["route"] == "rag_only"
        assert tool_sel["selected_tools"][0]["tool_name"] == "rag_search"
        assert "failed" in tool_sel["reasoning"].lower()


class TestToolSelectionRouting:
    """Tests for tool selection routing logic."""
    
    def test_tool_selection_decision_rag_only(self):
        """Test routing decision for rag_only."""
        mock_llm = MagicMock()
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "tool_selection": {
                "route": "rag_only",
                "selected_tools": [{"tool_name": "rag_search"}]
            }
        }
        
        decision = agent._tool_selection_decision(state)
        assert decision == "rag_only"
    
    def test_tool_selection_decision_tools_only(self):
        """Test routing decision for tools_only."""
        mock_llm = MagicMock()
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "tool_selection": {
                "route": "tools_only",
                "selected_tools": [{"tool_name": "jira_create"}]
            }
        }
        
        decision = agent._tool_selection_decision(state)
        assert decision == "tools_only"
    
    def test_tool_selection_decision_rag_and_tools(self):
        """Test routing decision for rag_and_tools."""
        mock_llm = MagicMock()
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "tool_selection": {
                "route": "rag_and_tools",
                "selected_tools": [
                    {"tool_name": "rag_search"},
                    {"tool_name": "jira_create"}
                ]
            }
        }
        
        decision = agent._tool_selection_decision(state)
        assert decision == "rag_and_tools"
    
    def test_tool_selection_decision_default_fallback(self):
        """Test routing decision defaults to rag_only if missing."""
        mock_llm = MagicMock()
        agent = QueryAgent(llm_client=mock_llm, rag_client=None)
        
        state: AgentState = {
            "tool_selection": {}  # Missing route
        }
        
        decision = agent._tool_selection_decision(state)
        assert decision == "rag_only"
