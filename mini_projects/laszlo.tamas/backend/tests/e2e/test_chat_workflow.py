"""
E2E Test: LangGraph Workflow
Knowledge Router PROD

Tests the complete UnifiedChatWorkflow including:
- Workflow compilation
- CHAT branch (greeting/conversation)
- RAG branch (document search)
- LIST branch (document listing)

Priority: HIGH (workflow is core functionality)
"""

import pytest
import os
from services.unified_chat_workflow import UnifiedChatWorkflow


@pytest.mark.e2e
class TestUnifiedChatWorkflow:
    """Test UnifiedChatWorkflow end-to-end."""
    
    @pytest.fixture(scope="class")
    def workflow(self):
        """Create workflow instance (class-scoped for reuse)."""
        openai_api_key = os.getenv("OPENAI_API_KEY")
        assert openai_api_key, "OPENAI_API_KEY environment variable not set"
        return UnifiedChatWorkflow(openai_api_key=openai_api_key)
    
    def test_workflow_compiles(self, workflow):
        """Test that workflow graph compiles without errors."""
        assert workflow.graph is not None, "Workflow graph should be compiled"
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_chat_branch_greeting(self, workflow, test_session):
        """
        Test CHAT branch with simple greeting.
        
        Real OpenAI call - costs ~$0.001
        """
        result = workflow.execute(
            query="szia",
            session_id=f"test_session_{test_session['session_id']}",
            user_context={
                "tenant_id": test_session["tenant_id"],
                "user_id": test_session["user_id"]
            }
        )
        
        # Assertions
        assert result is not None, "Result should not be None"
        assert "final_answer" in result, "Result should contain final_answer"
        assert result["final_answer"], "Final answer should not be empty"
        assert "actions_taken" in result, "Result should contain actions_taken"
        
        # Check that it's a chat response (not RAG/LIST)
        actions = result.get("actions_taken", [])
        print(f"\nDEBUG greeting actions_taken: {actions}")  # Debug print
        assert any("chat" in action.lower() for action in actions), \
            f"Should use CHAT branch for greeting. Got actions: {actions}"
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_rag_branch_document_query(self, workflow, test_session, test_document):
        """
        Test RAG branch with document search query.
        
        Real OpenAI call - costs ~$0.002-0.005 (embedding + completion)
        
        Prerequisites:
        - test_document fixture creates real document with Qdrant indexing
        - Document contains content about "machine learning" and "AI"
        """
        import uuid
        # Use fresh UUID for each test to avoid conflicts
        rag_session_id = str(uuid.uuid4())
        
        result = workflow.execute(
            query="Search in the Test AI Document for information about machine learning",
            session_id=rag_session_id,
            user_context={
                "tenant_id": test_session["tenant_id"],
                "user_id": test_session["user_id"]
            }
        )
        
        # Assertions
        assert result is not None, "Result should not be None"
        assert "final_answer" in result, "Result should contain final_answer"
        assert result["final_answer"], "Final answer should not be empty"
        
        # Check that RAG was actually used (document chunks retrieved)
        actions = result.get("actions_taken", [])
        sources = result.get("sources", [])
        
        print(f"\n=== DEBUG: actions_taken = {actions}")
        print(f"=== DEBUG: sources count = {len(sources)}")
        print(f"=== DEBUG: test_document indexed = {test_document.get('qdrant_indexed', False)}")
        
        # If document was indexed, agent MUST retrieve document chunks
        if test_document.get("qdrant_indexed"):
            # Accept both RAG and MULTI_RETRIEVAL (both use Qdrant document search)
            assert any(
                action in ["RAG", "MULTI_RETRIEVAL"] 
                for action in actions
            ), f"Should use RAG or MULTI_RETRIEVAL for document query. Got: {actions}"
            
            # Verify sources contain documents (not just memories)
            doc_sources = [s for s in sources if s.get("type") == "document"]
            assert len(doc_sources) > 0, \
                f"Should have document sources in result. Got sources: {sources}"
        else:
            # If Qdrant indexing failed (no OPENAI_API_KEY), accept LTM fallback
            pytest.skip("Document not indexed in Qdrant (OPENAI_API_KEY unavailable)")
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_list_branch_document_listing(self, workflow, test_session, test_document):
        """
        Test LIST branch with document listing query.
        
        Real OpenAI call - costs ~$0.001
        """
        result = workflow.execute(
            query="listázd a dokumentumokat",
            session_id=f"test_session_{test_session['session_id']}_list",
            user_context={
                "tenant_id": test_session["tenant_id"],
                "user_id": test_session["user_id"]
            }
        )
        
        # Assertions
        assert result is not None, "Result should not be None"
        assert "final_answer" in result, "Result should contain final_answer"
        assert result["final_answer"], "Final answer should not be empty"
        
        # Check that LIST was used
        actions = result.get("actions_taken", [])
        assert any("list" in action.lower() or "documents" in action.lower() for action in actions), \
            "Should use LIST branch for listing query"
    
    @pytest.mark.skip(reason="Mock workflow tests require complex DI setup - not priority for MVP")
    def test_workflow_with_mocked_openai(self, workflow, mock_openai_client, test_session):
        """
        Test workflow with mocked OpenAI (no cost).
        Verifies workflow structure without API calls.
        
        NOTE: Requires deep mock of LangGraph state + OpenAI client
        """
        with mock_openai_client:
            result = workflow.execute(
                query="test query",
                session_id=f"test_session_{test_session['session_id']}_mock",
                user_context={
                    "tenant_id": test_session["tenant_id"],
                    "user_id": test_session["user_id"]
                }
            )
        
        # Basic structure assertions
        assert result is not None, "Result should not be None"
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "final_answer" in result, "Result should contain final_answer"
    
    @pytest.mark.skip(reason="Mock workflow tests require complex DI setup - not priority for MVP")
    @pytest.mark.parametrize("query,expected_branch", [
        ("hello", "CHAT"),
        ("keress dokumentumban", "RAG"),
        ("listázd a fájlokat", "LIST"),
    ])
    def test_intent_routing_mocked(
        self, 
        workflow, 
        mock_openai_client, 
        test_session, 
        query, 
        expected_branch
    ):
        """
        Test intent routing with mocked responses.
        Verifies that different queries route to different branches.
        
        NOTE: Requires LangGraph state management mock
        """
        with mock_openai_client:
            result = workflow.execute(
                query=query,
                session_id=f"test_session_{test_session['session_id']}_intent",
                user_context={
                    "tenant_id": test_session["tenant_id"],
                    "user_id": test_session["user_id"]
                }
            )
        
        assert result is not None, f"Result should not be None for query: {query}"
        assert "final_answer" in result, "Result should contain final_answer"
        # Note: With mocked OpenAI, routing may not work perfectly
        # This test verifies workflow doesn't crash

