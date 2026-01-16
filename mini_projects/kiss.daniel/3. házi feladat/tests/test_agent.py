"""Integration tests for the agent graph."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.agent.graph import (
    read_user_prompt_node,
    decision_node,
    tool_node,
    answer_node,
    should_continue,
    create_graph
)
from src.agent.state import AgentState, Decision, ToolResult


class TestReadUserPromptNode:
    """Test cases for read_user_prompt_node."""
    
    def test_read_user_prompt_node(self):
        """Test that user prompt node returns state unchanged."""
        state = {
            "user_prompt": "Milyen az időjárás?",
            "tool_results": [],
            "iteration_count": 0,
            "decision": None,
            "final_answer": None
        }
        
        result = read_user_prompt_node(state)
        
        assert result == state


class TestDecisionNode:
    """Test cases for decision_node."""
    
    @patch('src.agent.graph.OllamaClient')
    def test_decision_node_call_tool(self, mock_ollama):
        """Test decision node deciding to call a tool."""
        mock_client = Mock()
        mock_client.invoke_json.return_value = {
            "action": "call_tool",
            "tool_name": "geocode_city",
            "tool_input": {"city": "Budapest", "country": "HU"},
            "reason": "Need coordinates"
        }
        mock_ollama.return_value = mock_client
        
        state = {
            "user_prompt": "Milyen az időjárás Budapesten?",
            "tool_results": [],
            "iteration_count": 0,
            "decision": None,
            "final_answer": None
        }
        
        result = decision_node(state)
        
        assert result["decision"] is not None
        assert result["decision"].action == "call_tool"
        assert result["decision"].tool_name == "geocode_city"
    
    @patch('src.agent.graph.OllamaClient')
    def test_decision_node_final_answer(self, mock_ollama):
        """Test decision node deciding to provide final answer."""
        mock_client = Mock()
        mock_client.invoke_json.return_value = {
            "action": "final_answer",
            "reason": "Have all information"
        }
        mock_ollama.return_value = mock_client
        
        state = {
            "user_prompt": "Szia",
            "tool_results": [],
            "iteration_count": 0,
            "decision": None,
            "final_answer": None
        }
        
        result = decision_node(state)
        
        assert result["decision"] is not None
        assert result["decision"].action == "final_answer"
    
    @patch('src.agent.graph.OllamaClient')
    def test_decision_node_invalid_response(self, mock_ollama):
        """Test decision node with invalid LLM response."""
        mock_client = Mock()
        mock_client.invoke_json.side_effect = ValueError("Invalid JSON")
        mock_ollama.return_value = mock_client
        
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": None,
            "final_answer": None
        }
        
        result = decision_node(state)
        
        # Should fallback to final_answer
        assert result["decision"] is not None
        assert result["decision"].action == "final_answer"


class TestToolNode:
    """Test cases for tool_node."""
    
    @patch('src.agent.graph.geocode_city')
    def test_tool_node_geocode(self, mock_geocode):
        """Test tool node executing geocode_city."""
        from src.agent.tools.geocode import GeocodeOutput
        
        mock_geocode.return_value = GeocodeOutput(
            success=True,
            name="Budapest",
            country="Hungary",
            latitude=47.4979,
            longitude=19.0402
        )
        
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": Decision(
                action="call_tool",
                tool_name="geocode_city",
                tool_input={"city": "Budapest"},
                reason="Need coordinates"
            ),
            "final_answer": None
        }
        
        result = tool_node(state)
        
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0].success is True
        assert result["tool_results"][0].tool_name == "geocode_city"
        assert result["iteration_count"] == 1
    
    @patch('src.agent.graph.get_weather')
    def test_tool_node_weather(self, mock_weather):
        """Test tool node executing get_weather."""
        from src.agent.tools.weather import WeatherOutput
        
        mock_weather.return_value = WeatherOutput(
            success=True,
            temperature_c=15.5,
            description="tiszta ég",
            wind_speed=3.5,
            humidity=65
        )
        
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": Decision(
                action="call_tool",
                tool_name="get_weather",
                tool_input={"latitude": 47.4979, "longitude": 19.0402},
                reason="Need weather"
            ),
            "final_answer": None
        }
        
        result = tool_node(state)
        
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0].success is True
        assert result["tool_results"][0].tool_name == "get_weather"
    
    def test_tool_node_invalid_tool(self):
        """Test tool node with invalid tool name."""
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": Decision(
                action="call_tool",
                tool_name="invalid_tool",
                tool_input={},
                reason="Test"
            ),
            "final_answer": None
        }
        
        result = tool_node(state)
        
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0].success is False
        # Error message can be either "Ismeretlen eszköz" or "Nincs érvényes eszköz hívás"
        assert result["tool_results"][0].error_message is not None


class TestAnswerNode:
    """Test cases for answer_node."""
    
    @patch('src.agent.graph.OllamaClient')
    def test_answer_node_success(self, mock_ollama):
        """Test answer node generating final answer."""
        mock_client = Mock()
        mock_client.invoke.return_value = "Budapesten 15°C van."
        mock_ollama.return_value = mock_client
        
        state = {
            "user_prompt": "Milyen az időjárás Budapesten?",
            "tool_results": [
                ToolResult(
                    tool_name="get_weather",
                    success=True,
                    data={"temperature_c": 15.0}
                )
            ],
            "iteration_count": 1,
            "decision": None,
            "final_answer": None
        }
        
        result = answer_node(state)
        
        assert result["final_answer"] is not None
        assert "15°C" in result["final_answer"]
    
    @patch('src.agent.graph.OllamaClient')
    def test_answer_node_error(self, mock_ollama):
        """Test answer node with LLM error."""
        mock_client = Mock()
        mock_client.invoke.side_effect = Exception("LLM error")
        mock_ollama.return_value = mock_client
        
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": None,
            "final_answer": None
        }
        
        result = answer_node(state)
        
        # Should have fallback answer (no weather data)
        assert result["final_answer"] is not None
        assert "nem tudok válaszolni" in result["final_answer"].lower()


class TestShouldContinue:
    """Test cases for should_continue router."""
    
    def test_should_continue_call_tool(self):
        """Test router choosing tool_node."""
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": Decision(
                action="call_tool",
                tool_name="geocode_city",
                tool_input={"city": "Budapest"},
                reason="Need coordinates"
            ),
            "final_answer": None
        }
        
        result = should_continue(state)
        
        assert result == "tool_node"
    
    def test_should_continue_final_answer(self):
        """Test router choosing answer_node."""
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 0,
            "decision": Decision(
                action="final_answer",
                reason="Done"
            ),
            "final_answer": None
        }
        
        result = should_continue(state)
        
        assert result == "answer_node"
    
    def test_should_continue_max_iterations(self):
        """Test router choosing answer_node when max iterations reached."""
        state = {
            "user_prompt": "Test",
            "tool_results": [],
            "iteration_count": 3,
            "decision": Decision(
                action="call_tool",
                tool_name="geocode_city",
                tool_input={"city": "Budapest"},
                reason="Need coordinates"
            ),
            "final_answer": None
        }
        
        result = should_continue(state)
        
        assert result == "answer_node"


class TestCreateGraph:
    """Test cases for graph creation."""
    
    def test_create_graph(self):
        """Test that graph is created successfully."""
        graph = create_graph()
        
        assert graph is not None
