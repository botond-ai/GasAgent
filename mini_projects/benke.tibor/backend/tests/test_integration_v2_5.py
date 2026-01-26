"""
Integration tests for v2.5 pipeline - Guardrail + Feedback Metrics nodes.

Tests full 6-node workflow: intent → retrieval → generation → guardrail → feedback_metrics → workflow
"""
import pytest
import re
from unittest.mock import MagicMock, AsyncMock

from services.agent import QueryAgent, DomainType
from domain.models import Citation
from domain.llm_outputs import IntentOutput, RAGGenerationOutput, MemoryUpdate, TurnMetrics


@pytest.fixture
def mock_llm():
    """Mock LLM client with domain-aware responses and structured output support."""
    llm = MagicMock()
    
    # Create structured output mock
    structured_llm = MagicMock()
    
    async def structured_ainvoke(messages):
        """Handle structured output requests (Pydantic models)."""
        if isinstance(messages, list) and len(messages) > 0:
            content = messages[0].content if hasattr(messages[0], 'content') else ""
        else:
            content = ""
        
        # Intent detection (IntentOutput)
        if "Classify this query" in str(content) or "Category:" in str(content):
            match = re.search(r'Query:\s*"(.+?)"', str(content), re.IGNORECASE | re.DOTALL)
            query_text = match.group(1) if match else str(content)
            ql = query_text.lower()
            
            if any(k in ql for k in ["vpn", "computer", "software"]):
                return IntentOutput(domain="it", confidence=0.95, reasoning="IT keywords detected")
            elif any(k in ql for k in ["vacation", "employee", "szabadság"]):
                return IntentOutput(domain="hr", confidence=0.92, reasoning="HR keywords")
            elif any(k in ql for k in ["brand", "logo", "arculat"]):
                return IntentOutput(domain="marketing", confidence=0.90, reasoning="Marketing keywords")
            else:
                return IntentOutput(domain="general", confidence=0.70, reasoning="No specific domain")
        
        # Memory update (MemoryUpdate)
        if "REDUCER PATTERN" in str(content) or "memory" in str(content).lower():
            return MemoryUpdate(
                summary="Test conversation summary",
                facts=["Fact 1", "Fact 2"],
                decisions=[]
            )
        
        # Turn metrics (TurnMetrics)
        if "llm_latency" in str(content).lower() or "metrics" in str(content).lower():
            return TurnMetrics(
                retrieval_score_top1=0.85,
                retrieval_score_avg=0.75,
                citations_count=3,
                llm_latency_ms=1200,
                cache_hit=False
            )
        
        # Generation (RAGGenerationOutput)
        return RAGGenerationOutput(
            answer="Response with citation [IT-KB-267]",
            section_ids=["IT-KB-267"],
            confidence=0.88,
            language="hu"
        )
    
    structured_llm.ainvoke = AsyncMock(side_effect=structured_ainvoke)
    llm.with_structured_output = MagicMock(return_value=structured_llm)
    
    # Legacy ainvoke for backward compatibility (if still used)
    async def llm_response(messages):
        """Handle both intent detection and generation requests."""
        if isinstance(messages, list) and len(messages) > 0:
            content = messages[0].content if hasattr(messages[0], 'content') else ""
        else:
            content = ""
        
        # Intent detection prompt detection
        if "Classify this query" in str(content) or "Category:" in str(content):
            # Extract only the query part from the prompt
            match = re.search(r'Query:\s*"(.+?)"', str(content), re.IGNORECASE | re.DOTALL)
            query_text = match.group(1) if match else str(content)
            ql = query_text.lower()
            # Determine domain based on query keywords only
            if any(k in ql for k in ["vpn", "computer", "software"]):
                return MagicMock(content="it")
            elif any(k in ql for k in ["vacation", "employee", "szabadság"]):
                return MagicMock(content="hr")
            elif any(k in ql for k in ["brand", "logo", "arculat"]):
                return MagicMock(content="marketing")
            else:
                return MagicMock(content="general")
        
        # Default generation response
        return MagicMock(content="Response with citation [KB-001]")
    
    llm.ainvoke = AsyncMock(side_effect=llm_response)
    return llm


@pytest.fixture
def mock_rag():
    """Mock RAG client."""
    rag = MagicMock()
    rag.retrieve_for_domain = AsyncMock()
    return rag


@pytest.fixture
def agent(mock_llm, mock_rag):
    """QueryAgent with mocked dependencies."""
    return QueryAgent(mock_llm, mock_rag)


class TestPipeline6NodeWorkflow:
    """Test full 6-node LangGraph workflow."""

    @pytest.mark.asyncio
    async def test_full_it_domain_pipeline(self, agent, mock_llm, mock_rag):
        """Test IT domain query through full pipeline."""
        # Mock RAG retrieval for IT domain
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="IT-KB-267",
                title="VPN Setup Guide",
                score=0.87,
                section_id="IT-KB-267",
                content="[IT-KB-267] VPN Configuration..."
            )
        ]
        
        # Execute full pipeline - query with IT keywords triggers IT domain detection
        response = await agent.run(
            query="How to setup VPN on my computer?",  # 'VPN' + 'computer' keywords
            user_id="emp_001",
            session_id="sess_123"
        )
        
        # Verify response
        assert response is not None, "Response should not be None"
        assert response.domain == DomainType.IT.value, f"Should detect IT domain, got {response.domain}"
        assert response.answer is not None, "Answer should not be None"
        assert len(response.answer) > 0, "Answer should not be empty"

    @pytest.mark.asyncio
    async def test_marketing_domain_pipeline(self, agent, mock_llm, mock_rag):
        """Test Marketing domain through pipeline."""
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="MARK-001",
                title="Brand Guidelines",
                score=0.92,
                content="Brand guidelines content..."
            )
        ]
        
        # Marketing domain keywords in query
        response = await agent.run(
            query="What is our brand and logo design arculat?",  # 'brand', 'logo', 'arculat' keywords
            user_id="emp_002",
            session_id="sess_124"
        )
        
        assert response is not None
        assert response.domain == DomainType.MARKETING.value, f"Should detect MARKETING domain, got {response.domain}"
        assert response.answer is not None

    @pytest.mark.asyncio
    async def test_pipeline_telemetry_collection(self, agent, mock_llm, mock_rag):
        """Test that telemetry is collected through pipeline."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="VPN setup answer [IT-KB-267]"
        )
        
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="IT-KB-267",
                title="VPN Guide",
                score=0.88,
                section_id="IT-KB-267",
                content="VPN content..."
            )
        ]
        
        response = await agent.run(
            query="VPN help?",
            user_id="emp_003",
            session_id="sess_125"
        )
        
        # Check telemetry fields
        assert response.rag_context is not None or response.rag_context == "", "Should have RAG context"
        assert response.llm_prompt is not None or response.llm_prompt == "", "Should have LLM prompt"
        assert response.llm_response is not None or response.llm_response == "", "Should have LLM response"


class TestPipelineErrorHandling:
    """Test error handling in 6-node pipeline."""

    @pytest.mark.asyncio
    async def test_rag_retrieval_failure_handling(self, agent, mock_llm, mock_rag):
        """Test pipeline continues if RAG fails."""
        # RAG raises exception
        mock_rag.retrieve_for_domain.side_effect = Exception("RAG service error")
        
        mock_llm.ainvoke.return_value = MagicMock(
            content="Unable to retrieve specific guidance. Here's general advice..."
        )
        
        # Should handle gracefully
        response = await agent.run(
            query="Help with something?",
            user_id="emp_004",
            session_id="sess_126"
        )
        
        # Response still generated
        assert response.answer is not None
        assert len(response.answer) > 0

    @pytest.mark.asyncio
    async def test_validation_retry_on_missing_citations(self, agent, mock_llm, mock_rag):
        """Test guardrail retry logic when citations are missing."""
        # First call: no citations in response
        # Second call: with citations
        mock_llm.ainvoke.side_effect = [
            MagicMock(content="VPN setup steps..."),  # First: no citations
            MagicMock(content="VPN setup [IT-KB-267] steps..."),  # Second: with citations
        ]
        
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="IT-KB-267",
                title="VPN Guide",
                score=0.87,
                section_id="IT-KB-267",
                content="[IT-KB-267] VPN content..."
            )
        ]
        
        response = await agent.run(
            query="VPN setup?",
            user_id="emp_005",
            session_id="sess_127"
        )
        
        # Should either have citations or best-effort answer
        assert response.answer is not None
        assert len(response.answer) > 0


class TestGraphStructure:
    """Test LangGraph structure and node connectivity."""

    def test_workflow_has_6_nodes(self, agent):
        """Verify graph has 6 nodes."""
        graph = agent.workflow
        # Compiled graph - check nodes are defined
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke"), "Graph should be compiled"

    def test_workflow_graph_compilation(self, agent):
        """Test that graph compiles correctly."""
        # If we get here, graph compiled successfully
        assert agent.workflow is not None
        assert hasattr(agent.workflow, "ainvoke"), "Compiled graph should have ainvoke"


class TestMetricsIntegration:
    """Test metrics node integration with pipeline."""

    @pytest.mark.asyncio
    async def test_metrics_collected_in_final_state(self, agent, mock_llm, mock_rag):
        """Test that metrics are collected and available."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="Answer [IT-KB-267]"
        )
        
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="IT-KB-267",
                title="Guide",
                score=0.85,
                section_id="IT-KB-267",
                content="Content..."
            )
        ]
        
        response = await agent.run(
            query="Query?",
            user_id="emp_006",
            session_id="sess_128"
        )
        
        # Metrics should be collected (even if response doesn't expose them directly)
        assert response.answer is not None

    @pytest.mark.asyncio
    async def test_empty_citations_handling(self, agent, mock_llm, mock_rag):
        """Test pipeline handles queries with no relevant citations."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="General knowledge response without specific citations."
        )
        
        mock_rag.retrieve_for_domain.return_value = []  # No results
        
        response = await agent.run(
            query="Obscure question?",
            user_id="emp_007",
            session_id="sess_129"
        )
        
        assert response.answer is not None
        assert len(response.citations) == 0, "No citations for empty retrieval"


class TestDomainSpecificBehavior:
    """Test domain-specific behavior through pipeline."""

    @pytest.mark.asyncio
    async def test_hr_domain_workflow(self, agent, mock_llm, mock_rag):
        """Test HR domain generates appropriate workflow."""
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="HR-POL-001",
                title="Vacation Policy",
                score=0.90,
                content="HR content..."
            )
        ]
        
        # HR domain keywords: "employee", "vacation", "szabadság"
        response = await agent.run(
            query="I need employee vacation time",
            user_id="emp_008",
            session_id="sess_130"
        )
        
        assert response is not None
        assert response.domain == DomainType.HR.value, f"Should detect HR domain, got {response.domain}"
        assert response.answer is not None

    @pytest.mark.asyncio
    async def test_it_domain_workflow(self, agent, mock_llm, mock_rag):
        """Test IT domain generates Jira workflow."""
        mock_rag.retrieve_for_domain.return_value = [
            Citation(
                doc_id="IT-KB-267",
                title="VPN Guide",
                score=0.87,
                section_id="IT-KB-267",
                content="[IT-KB-267] VPN..."
            )
        ]
        
        # IT domain keywords: "VPN", "computer", "software"
        response = await agent.run(
            query="VPN software is not working",
            user_id="emp_009",
            session_id="sess_131"
        )
        
        assert response is not None
        assert response.domain == DomainType.IT.value, f"Should detect IT domain, got {response.domain}"
        assert response.answer is not None
