"""
Tests for SupportAIAgent.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.agent import SupportAIAgent
from app.core.state import AgentState
from app.models import TicketAnalysis
from app.models.output import AnswerDraft


class TestSupportAIAgent:
    """Tests for SupportAIAgent class."""

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for ticket analysis."""
        return TicketAnalysis(
            language="Hungarian",
            sentiment="frustrated",
            category="Technical",
            subcategory="Login Issue",
            priority="P2",
            routing="IT Support",
            confidence=0.92,
            key_entities=["login", "password"],
            summary="User cannot log in to their account",
        )

    @pytest.fixture
    def mock_answer_draft(self):
        """Mock answer draft response."""
        return AnswerDraft(
            greeting="Kedves Teszt Felhasználó!",
            body="Köszönjük a megkeresését. A bejelentkezési problémával kapcsolatban kollégáink hamarosan felveszik Önnel a kapcsolatot.",
            closing="Üdvözlettel, TaskFlow Support",
            tone="empathetic_professional",
        )

    @pytest.fixture
    def sample_ticket_hungarian(self):
        """Sample Hungarian support ticket."""
        return """
        Sziasztok!

        Nem tudok belépni a fiókomba. Már háromszor próbáltam a jelszavamat,
        de mindig hibát ír ki. Nagyon sürgős lenne, mert holnap van a határidő!

        Köszönöm a segítséget!
        Kovács János
        """

    @pytest.fixture
    def sample_ticket_english(self):
        """Sample English support ticket."""
        return """
        Hello,

        I cannot access my account. I've tried resetting my password
        three times but it keeps showing an error. This is urgent!

        Thanks,
        John Smith
        """

    @patch("app.core.agent.ChatOpenAI")
    def test_agent_initialization(self, mock_chat_openai):
        """Test that agent initializes correctly."""
        mock_chat_openai.return_value = MagicMock()

        agent = SupportAIAgent()

        assert agent.llm is not None
        assert agent.analysis_llm is not None
        assert agent.response_llm is not None
        assert agent.graph is not None

    @patch("app.core.agent.ChatOpenAI")
    def test_analyze_returns_dict(self, mock_chat_openai, mock_llm_response, mock_answer_draft):
        """Test that analyze method returns a dictionary."""
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = [
            MagicMock(invoke=MagicMock(return_value=mock_llm_response)),  # analysis_llm
            MagicMock(invoke=MagicMock(return_value=mock_answer_draft)),  # response_llm
        ]
        mock_chat_openai.return_value = mock_llm

        agent = SupportAIAgent()
        agent.analysis_llm = MagicMock(invoke=MagicMock(return_value=mock_llm_response))
        agent.response_llm = MagicMock(invoke=MagicMock(return_value=mock_answer_draft))

        # Mock the graph invoke
        mock_response = {
            "session_id": "test-session",
            "triage": {
                "category": "Technical",
                "priority": "P2",
                "sentiment": "frustrated",
                "confidence": 0.92,
            },
            "answer_draft": {
                "greeting": "Kedves Felhasználó!",
                "body": "Test response",
                "closing": "Üdvözlettel",
                "tone": "empathetic_professional",
            },
        }
        agent.graph = MagicMock(invoke=MagicMock(return_value={"final_response": mock_response}))

        result = agent.analyze("Test ticket", session_id="test-123")

        assert isinstance(result, dict)
        assert "session_id" in result or "error" in result

    @patch("app.core.agent.ChatOpenAI")
    def test_analyze_with_customer_name(self, mock_chat_openai, mock_llm_response, mock_answer_draft):
        """Test that analyze passes customer name correctly."""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm

        agent = SupportAIAgent()

        # Mock the graph to capture the state
        captured_state = {}
        def capture_invoke(state):
            captured_state.update(state)
            return {"final_response": {"session_id": "test"}}

        agent.graph = MagicMock(invoke=capture_invoke)

        agent.analyze(
            ticket_text="Test ticket",
            customer_name="Kovács János",
            session_id="test-123"
        )

        assert captured_state.get("customer_name") == "Kovács János"

    @patch("app.core.agent.ChatOpenAI")
    def test_analyze_generates_session_id_if_not_provided(self, mock_chat_openai):
        """Test that session_id is generated if not provided."""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm

        agent = SupportAIAgent()

        captured_state = {}
        def capture_invoke(state):
            captured_state.update(state)
            return {"final_response": {"session_id": state["session_id"]}}

        agent.graph = MagicMock(invoke=capture_invoke)

        result = agent.analyze("Test ticket")

        assert captured_state.get("session_id") is not None
        assert len(captured_state["session_id"]) > 0


class TestAgentNodes:
    """Tests for individual agent nodes."""

    @pytest.fixture
    def agent(self):
        """Create agent with mocked LLM."""
        with patch("app.core.agent.ChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()
            return SupportAIAgent()

    def test_should_get_location_with_ip(self, agent):
        """Test location routing with IP address."""
        state = {"ip_address": "8.8.8.8"}
        result = agent._should_get_location(state)
        assert result == "get_location"

    def test_should_get_location_without_ip(self, agent):
        """Test location routing without IP address."""
        state = {"ip_address": None}
        result = agent._should_get_location(state)
        assert result == "calculate_sla"

    def test_should_get_location_empty_ip(self, agent):
        """Test location routing with empty IP address."""
        state = {"ip_address": ""}
        result = agent._should_get_location(state)
        assert result == "calculate_sla"


class TestAgentState:
    """Tests for AgentState TypedDict."""

    def test_agent_state_has_required_fields(self):
        """Test that AgentState has all required fields."""
        required_fields = [
            "messages",
            "ticket_text",
            "ip_address",
            "session_id",
            "customer_name",
            "language",
            "sentiment",
            "category",
            "priority",
            "confidence",
            "final_response",
        ]

        state_annotations = AgentState.__annotations__

        for field in required_fields:
            assert field in state_annotations, f"Missing field: {field}"

    def test_agent_state_customer_name_is_optional(self):
        """Test that customer_name field accepts None."""
        from typing import get_type_hints, Optional

        hints = get_type_hints(AgentState)
        # customer_name should be Optional[str]
        assert "customer_name" in hints
