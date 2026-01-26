import pytest
from unittest.mock import AsyncMock, MagicMock
from domain.interfaces import ILLMClient, IVectorDBClient, ITicketClient, IConversationRepository
from domain.models import Analysis, TriageDecision, AnswerDraft

@pytest.fixture
def mock_llm():
    llm_client = MagicMock(spec=ILLMClient)
    llm_client.generate = AsyncMock()
    llm_client.generate_structured = AsyncMock()
    llm_client.bind_tools = MagicMock()
    
    # Mock the underlying llm attribute which is accessed in the agent
    mock_underlying_llm = AsyncMock()
    mock_underlying_llm.ainvoke = AsyncMock()
    
    llm_client.llm = mock_underlying_llm
    
    return llm_client

@pytest.fixture
def mock_vector_db():
    db = MagicMock(spec=IVectorDBClient)
    db.search = AsyncMock(return_value=[
        {"source": "test_doc.txt", "text": "This is a test context.", "score": 0.9}
    ])
    db.upsert = AsyncMock()
    return db

@pytest.fixture
def mock_ticket_client():
    client = MagicMock(spec=ITicketClient)
    client.create_ticket = AsyncMock(return_value={"id": "TICKET-123", "status": "created"})
    return client

@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=IConversationRepository)
    repo.add_message = AsyncMock()
    repo.get_history = AsyncMock(return_value=[])
    repo.clear_history = AsyncMock()
    return repo
