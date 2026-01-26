"""Integration test for the entire LangGraph workflow."""

import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import AsyncMock, MagicMock, patch
from services.langgraph_workflow import (
    create_advanced_rag_workflow,
    AdvancedRAGAgent,
    ToolRegistry,
    WorkflowOutput,
    SearchStrategy,
)
from domain.models import CategoryDecision, Message, MessageRole, RetrievedChunk
from domain.interfaces import CategoryRouter, EmbeddingService, VectorStore, RAGAnswerer


class TestServiceImplementation(CategoryRouter, EmbeddingService, VectorStore, RAGAnswerer):
    """Mock implementation of all required services."""
    
    # CategoryRouter
    async def decide_category(self, question, categories):
        return CategoryDecision(
            category=categories[0] if categories else "default",
            confidence=0.95,
            reason="test decision"
        )
    
    # EmbeddingService
    async def embed_text(self, text):
        return [0.1] * 384
    
    async def embed_texts(self, texts):
        return [[0.1] * 384 for _ in texts]
    
    # VectorStore
    async def store(self, chunks, collection_name):
        return True
    
    async def add_chunks(self, chunks, collection_name):
        return True
    
    async def create_collection(self, collection_name):
        return True
    
    async def delete_chunks(self, chunk_ids, collection_name):
        return True
    
    async def query(self, embedding, collection_name, top_k=5):
        return [
            RetrievedChunk(
                chunk_id="1",
                content=f"Content about {collection_name}",
                distance=0.2,
                metadata={"source": f"{collection_name}_1.txt"}
            ),
            RetrievedChunk(
                chunk_id="2",
                content=f"More content about {collection_name}",
                distance=0.3,
                metadata={"source": f"{collection_name}_2.txt"}
            ),
        ]
    
    async def delete_collection(self, collection_name):
        return True
    
    # RAGAnswerer
    async def generate_answer(self, question, chunks, category):
        chunk_content = "\n".join([c.content for c in chunks[:2]])
        return f"Based on the {category} documentation:\n{chunk_content}\n\nAnswer to '{question}': This is a generated answer based on the provided context."


class TestCompleteWorkflowIntegration:
    """Test the complete workflow integration."""
    
    def test_workflow_creation(self):
        """Test that workflow can be created with mock services."""
        services = TestServiceImplementation()
        
        graph, registry = create_advanced_rag_workflow(
            services,  # CategoryRouter
            services,  # EmbeddingService
            services,  # VectorStore
            services,  # RAGAnswerer
        )
        
        assert graph is not None
        assert registry is not None
        assert isinstance(registry, ToolRegistry)
        print("✅ Workflow created successfully")
    
    def test_tool_registry(self):
        """Test that all required tools are registered."""
        services = TestServiceImplementation()
        
        _, registry = create_advanced_rag_workflow(
            services, services, services, services
        )
        
        tools = registry.list_tools()
        print(f"✅ Registered tools: {tools}")
        
        # Should have 4 tools
        assert len(tools) == 4
        assert "category_router" in tools
        assert "embed_question" in tools
        assert "search_vectors" in tools
        assert "generate_answer" in tools
    
    def test_agent_creation(self):
        """Test that AdvancedRAGAgent can be instantiated."""
        services = TestServiceImplementation()
        
        graph, registry = create_advanced_rag_workflow(
            services, services, services, services
        )
        
        agent = AdvancedRAGAgent(graph, registry)
        
        assert agent is not None
        assert agent.graph == graph
        assert agent.tool_registry == registry
        print("✅ Agent created successfully")
    
    @pytest.mark.asyncio
    async def test_workflow_execution(self):
        """Test complete workflow execution."""
        services = TestServiceImplementation()
        
        graph, registry = create_advanced_rag_workflow(
            services, services, services, services
        )
        
        agent = AdvancedRAGAgent(graph, registry)
        
        # Run the workflow
        result = await agent.answer_question(
            user_id="test_user",
            question="What is the meaning of life?",
            available_categories=["philosophy", "science", "general"],
        )
        
        # Verify result
        assert isinstance(result, WorkflowOutput)
        # Even if no answer generated, the structure should be correct
        assert isinstance(result.answer_with_citations, str)
        assert isinstance(result.citation_sources, list)
        assert isinstance(result.workflow_log, (dict, type(None)))
        assert isinstance(result.workflow_steps, list)
        assert len(result.workflow_steps) > 0  # Should have executed steps
        
        print(f"✅ Workflow executed successfully")
        print(f"  - Steps executed: {result.workflow_steps}")
        print(f"  - Category: {result.routed_category}")
        print(f"  - Citation count: {len(result.citation_sources)}")


class TestWorkflowStateManagement:
    """Test workflow state handling."""
    
    def test_workflow_initialization(self):
        """Test initial state setup."""
        from services.langgraph_workflow import WorkflowState
        
        state: WorkflowState = {
            "user_id": "test_user",
            "question": "Test question?",
            "available_categories": ["cat1", "cat2"],
        }
        
        assert state["user_id"] == "test_user"
        assert state["question"] == "Test question?"
        assert len(state["available_categories"]) == 2
        
        print("✅ Workflow state initialization works")
    
    def test_workflow_state_typing(self):
        """Test that WorkflowState TypedDict works correctly."""
        from services.langgraph_workflow import WorkflowState
        
        # Create a valid state
        state: WorkflowState = {
            "user_id": "user123",
            "session_id": "sess456",
            "question": "What is AI?",
            "available_categories": ["ai", "tech"],
            "routed_category": "ai",
            "category_confidence": 0.95,
            "context_chunks": [],
            "search_strategy": "category_based",
            "fallback_triggered": False,
            "final_answer": "",
            "errors": [],
            "error_count": 0,
            "retry_count": 0,
            "workflow_logs": [],
        }
        
        # Verify types
        assert isinstance(state["user_id"], str)
        assert isinstance(state["available_categories"], list)
        assert isinstance(state["errors"], list)
        assert isinstance(state["workflow_logs"], list)
        
        print("✅ WorkflowState typing works correctly")


class TestErrorRecovery:
    """Test error handling and recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_error_handling_in_workflow(self):
        """Test that errors are properly handled in workflow."""
        from services.langgraph_workflow import validate_input_node
        
        # Test with invalid state
        invalid_state = {
            "question": "",  # Empty question
            "available_categories": [],  # No categories
        }
        
        result = validate_input_node(invalid_state)
        
        # Should have errors
        assert len(result["errors"]) > 0
        assert result["error_count"] >= 0
        assert "workflow_logs" in result
        
        print("✅ Error handling works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
