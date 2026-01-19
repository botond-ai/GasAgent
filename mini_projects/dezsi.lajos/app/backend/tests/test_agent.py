import pytest
import json
from unittest.mock import AsyncMock, ANY
from services.agent import TriageAgent
from services.chat_service import ChatService
from domain.models import Analysis, TriageDecision, AnswerDraft, TicketCreate

class TestTriageAgent:
    
    @pytest.mark.asyncio
    async def test_agent_workflow_end_to_end(self, mock_llm, mock_vector_db, mock_ticket_client):
        # Setup Mocks
        analysis_result = Analysis(
            summary="User has a login issue",
            intent="Technical Support",
            complexity="Medium"
        )
        triage_result = TriageDecision(
            responsible_party="Tech Support Team",
            reasoning="Requires DB check",
            escalation_needed=True,
            support_tier="Tier 2 Support"
        )
        draft_result = AnswerDraft(
            body="I have escalated your issue to Tier 2. Ticket ID: TICKET-123",
            citations=["doc1"]
        )
        
        # side_effect order: Analysis, TriageDecision, AnswerDraft
        mock_llm.generate_structured.side_effect = [analysis_result, triage_result, draft_result]
        
        # Mock tool call response from the LLM
        from langchain_core.messages import AIMessage
        mock_tool_call_msg = AIMessage(content="", tool_calls=[
            {
                "name": "create_ticket_tool", 
                "args": {
                    "title": "[Tier 2 Support] User has a login issue", 
                    "description": "Intent: Technical Support\n\nReasoning: Requires DB check\n\nComplexity: Medium", 
                    "priority": "Medium", 
                    "category": "Technical Support", 
                    "tags": ["Tier 2 Support", "Technical Support"]
                }, 
                "id": "call_123"
            }
        ])
        mock_llm.llm.ainvoke.return_value = mock_tool_call_msg
        
        agent = TriageAgent(llm_client=mock_llm, vector_db=mock_vector_db, ticket_client=mock_ticket_client)
        
        # Run
        result = await agent.run("I cannot login to my account")
        
        # Verify
        assert result["analysis"] == analysis_result.model_dump()
        assert result["triage_decision"] == triage_result.model_dump()
        assert result["answer_draft"] == draft_result.model_dump()
        assert result["ticket_created"] == {"id": "TICKET-123", "status": "created"}
        
        
        # Verify calls
        assert mock_llm.generate_structured.call_count == 3
        
        # With tool calling, create_ticket is called by the ToolNode, which uses the ticket_client.
        # Ensure the client was called with the arguments from the tool call.
        mock_ticket_client.create_ticket.assert_called_once()
        
        # Verify ticket details
        args, _ = mock_ticket_client.create_ticket.call_args
        ticket_arg = args[0]
        assert isinstance(ticket_arg, TicketCreate)
        assert ticket_arg.title == "[Tier 2 Support] User has a login issue"

    @pytest.mark.asyncio
    async def test_agent_no_escalation(self, mock_llm, mock_vector_db, mock_ticket_client):
        # Setup Mocks for Tier 1 (no escalation)
        analysis_result = Analysis(
            summary="User needs password reset",
            intent="Password Reset",
            complexity="Low"
        )
        triage_result = TriageDecision(
            responsible_party="Helpdesk",
            reasoning="Standard procedure",
            escalation_needed=False, # No escalation
            support_tier="Tier 1 Support"
        )
        draft_result = AnswerDraft(
            body="Here is how you reset your password...",
            citations=[]
        )
        
        mock_llm.generate_structured.side_effect = [analysis_result, triage_result, draft_result]
        
        agent = TriageAgent(llm_client=mock_llm, vector_db=mock_vector_db, ticket_client=mock_ticket_client)
        
        # Run
        result = await agent.run("How do I reset my password?")
        
        # Verify
        assert result["ticket_created"] is None
        mock_ticket_client.create_ticket.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_agent_escalation_logic_without_ticket_client(self, mock_llm, mock_vector_db):
        # Setup - Escalation needed but NO ticket_client provided
        analysis_result = Analysis(summary="Bug", intent="Bug", complexity="High")
        triage_result = TriageDecision(responsible_party="Eng", reasoning="Bug", escalation_needed=True, support_tier="Tier 3 Support")
        draft_result = AnswerDraft(body="We are looking into it.", citations=[])
        
        mock_llm.generate_structured.side_effect = [analysis_result, triage_result, draft_result]
        
        # Initialize agent WITHOUT ticket_client
        agent = TriageAgent(llm_client=mock_llm, vector_db=mock_vector_db, ticket_client=None)
        
        result = await agent.run("Refactor the backend")
        
        assert result["ticket_created"] is None

class TestChatService:
    @pytest.mark.asyncio
    async def test_process_message(self, mock_repo, mock_llm, mock_vector_db):
        # Setup Agent Mock returns
        analysis = Analysis(summary="Hi", intent="Greeting", complexity="Low")
        triage = TriageDecision(responsible_party="None", reasoning="None", escalation_needed=False, support_tier="Tier 1 Support")
        draft = AnswerDraft(body="Hello there!", citations=[])
        
        mock_llm.generate_structured.side_effect = [analysis, triage, draft]
        
        agent = TriageAgent(llm_client=mock_llm, vector_db=mock_vector_db)
        service = ChatService(agent=agent, repo=mock_repo)
        
        # Run
        response = await service.process_message("conv-1", "Hello")
        
        # Verify
        assert response.response == "Hello there!"
        assert response.conversation_id == "conv-1"
        
        # Verify repo calls
        assert mock_repo.add_message.call_count == 2 # User msg + Asst msg
        # Check first call is user message
        call1 = mock_repo.add_message.call_args_list[0]
        assert call1[0][0] == "conv-1"
        assert call1[0][1].role == "user"
        assert call1[0][1].content == "Hello"
        
        # Check second call is assistant message
        call2 = mock_repo.add_message.call_args_list[1]
        assert call2[0][0] == "conv-1"
        assert call2[0][1].role == "assistant"
        assert call2[0][1].content == "Hello there!"
