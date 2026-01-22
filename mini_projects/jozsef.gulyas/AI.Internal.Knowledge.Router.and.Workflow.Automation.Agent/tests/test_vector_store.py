import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.vector_store import VectorStore, SearchResult, Domain


@pytest.fixture
def mock_openai_gateway():
    gateway = MagicMock()
    gateway.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])
    return gateway


@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.add = MagicMock()
    collection.get = MagicMock(return_value={"ids": [], "metadatas": []})
    collection.delete = MagicMock()
    collection.query = MagicMock(return_value={
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    })
    return collection


@pytest.fixture
def mock_chroma_client(mock_collection):
    with patch("chromadb.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_or_create_collection = MagicMock(return_value=mock_collection)
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def vector_store(mock_openai_gateway, mock_chroma_client):
    return VectorStore(openai_gateway=mock_openai_gateway)


class TestVectorStoreInit:
    def test_init_sets_openai_gateway(self, vector_store, mock_openai_gateway):
        assert vector_store.openai_gateway == mock_openai_gateway

    def test_init_creates_collections_for_all_domains(self, mock_openai_gateway, mock_chroma_client):
        store = VectorStore(openai_gateway=mock_openai_gateway)

        assert len(store.collections) == len(Domain)
        for domain in Domain:
            assert domain in store.collections

    def test_init_creates_in_memory_client_by_default(self, mock_openai_gateway):
        with patch("chromadb.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_or_create_collection = MagicMock(return_value=MagicMock())
            mock_client_class.return_value = mock_client

            VectorStore(openai_gateway=mock_openai_gateway)

            mock_client_class.assert_called_once()

    def test_init_creates_persistent_client_when_path_provided(self, mock_openai_gateway):
        with patch("chromadb.PersistentClient") as mock_persistent_class:
            mock_client = MagicMock()
            mock_client.get_or_create_collection = MagicMock(return_value=MagicMock())
            mock_persistent_class.return_value = mock_client

            VectorStore(openai_gateway=mock_openai_gateway, persist_path="/tmp/chroma")

            mock_persistent_class.assert_called_once()


class TestAddDocumentChunk:
    @pytest.mark.asyncio
    async def test_gets_embedding_for_text(self, vector_store, mock_openai_gateway):
        await vector_store.add_document_chunk(
            text="Test document content",
            domain=Domain.HR,
            metadata={"doc_id": "doc1", "title": "Test", "source": "/path"}
        )

        mock_openai_gateway.get_embedding.assert_called_once_with("Test document content")

    @pytest.mark.asyncio
    async def test_adds_chunk_to_correct_domain_collection(self, vector_store, mock_collection):
        await vector_store.add_document_chunk(
            text="HR policy document",
            domain=Domain.HR,
            metadata={"doc_id": "hr_doc1", "title": "HR Policy", "source": "/path/hr.md"}
        )

        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["ids"] == ["hr_doc1"]
        assert call_kwargs["documents"] == ["HR policy document"]
        assert call_kwargs["embeddings"] == [[0.1, 0.2, 0.3, 0.4, 0.5]]

    @pytest.mark.asyncio
    async def test_returns_doc_id(self, vector_store):
        doc_id = await vector_store.add_document_chunk(
            text="Test content",
            domain=Domain.IT,
            metadata={"doc_id": "my_doc_id", "title": "Test", "source": "/path"}
        )

        assert doc_id == "my_doc_id"

    @pytest.mark.asyncio
    async def test_generates_uuid_when_doc_id_not_provided(self, vector_store, mock_collection):
        with patch("uuid.uuid4", return_value="generated-uuid"):
            doc_id = await vector_store.add_document_chunk(
                text="Test content",
                domain=Domain.FINANCE,
                metadata={"title": "Test", "source": "/path"}
            )

        assert doc_id == "generated-uuid"

    @pytest.mark.asyncio
    async def test_stores_metadata_correctly(self, vector_store, mock_collection):
        await vector_store.add_document_chunk(
            text="Content",
            domain=Domain.LEGAL,
            metadata={
                "doc_id": "legal1",
                "title": "Legal Agreement",
                "source": "/docs/legal.md",
                "hash": "abc123"
            }
        )

        call_kwargs = mock_collection.add.call_args.kwargs
        metadata = call_kwargs["metadatas"][0]
        assert metadata["doc_id"] == "legal1"
        assert metadata["title"] == "Legal Agreement"
        assert metadata["source"] == "/docs/legal.md"
        assert metadata["hash"] == "abc123"


class TestFindByTitle:
    def test_returns_document_when_found(self, vector_store, mock_collection):
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "metadatas": [{"title": "Test Doc", "hash": "abc123"}]
        }

        result = vector_store.find_by_title("Test Doc", Domain.HR)

        assert result is not None
        assert result["ids"] == ["doc1", "doc2"]
        assert result["metadata"]["title"] == "Test Doc"
        assert result["metadata"]["hash"] == "abc123"

    def test_returns_none_when_not_found(self, vector_store, mock_collection):
        mock_collection.get.return_value = {"ids": [], "metadatas": []}

        result = vector_store.find_by_title("Nonexistent Doc", Domain.HR)

        assert result is None

    def test_queries_correct_domain_collection(self, vector_store, mock_collection):
        mock_collection.get.return_value = {"ids": [], "metadatas": []}

        vector_store.find_by_title("Test", Domain.MARKETING)

        mock_collection.get.assert_called_once_with(
            where={"title": "Test"},
            include=["metadatas"]
        )


class TestDeleteByTitle:
    def test_deletes_chunks_when_found(self, vector_store, mock_collection):
        mock_collection.get.return_value = {
            "ids": ["chunk1", "chunk2", "chunk3"],
            "metadatas": [{"title": "Doc"}]
        }

        deleted_count = vector_store.delete_by_title("Doc", Domain.HR)

        assert deleted_count == 3
        mock_collection.delete.assert_called_once_with(ids=["chunk1", "chunk2", "chunk3"])

    def test_returns_zero_when_not_found(self, vector_store, mock_collection):
        mock_collection.get.return_value = {"ids": [], "metadatas": []}

        deleted_count = vector_store.delete_by_title("Nonexistent", Domain.HR)

        assert deleted_count == 0
        mock_collection.delete.assert_not_called()


class TestSearch:
    @pytest.mark.asyncio
    async def test_gets_embedding_for_query(self, vector_store, mock_openai_gateway, mock_collection):
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        await vector_store.search("search query", Domain.HR)

        mock_openai_gateway.get_embedding.assert_called_once_with("search query")

    @pytest.mark.asyncio
    async def test_queries_correct_domain_with_top_k(self, vector_store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        await vector_store.search("query", Domain.IT, top_k=10)

        mock_collection.query.assert_called_once()
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["n_results"] == 10

    @pytest.mark.asyncio
    async def test_returns_search_results(self, vector_store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["First doc content", "Second doc content"]],
            "metadatas": [[
                {"doc_id": "doc1", "title": "First", "source": "/first.md"},
                {"doc_id": "doc2", "title": "Second", "source": "/second.md"}
            ]],
            "distances": [[0.1, 0.3]]  # cosine distance
        }

        results = await vector_store.search("query", Domain.HR)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].text == "First doc content"
        assert results[0].doc_id == "doc1"
        assert results[0].title == "First"
        assert results[0].score == 0.9  # 1 - 0.1 = 0.9
        assert results[0].domain == Domain.HR

    @pytest.mark.asyncio
    async def test_converts_distance_to_similarity_score(self, vector_store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["Content"]],
            "metadatas": [[{"doc_id": "doc1", "title": "Doc", "source": "/doc.md"}]],
            "distances": [[0.25]]  # Distance of 0.25
        }

        results = await vector_store.search("query", Domain.HR)

        assert results[0].score == 0.75  # 1 - 0.25 = 0.75

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_results(self, vector_store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        results = await vector_store.search("query", Domain.HR)

        assert results == []


class TestSearchAll:
    @pytest.mark.asyncio
    async def test_searches_all_domains(self, vector_store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        results = await vector_store.search_all("query", top_k=3)

        assert len(results) == len(Domain)
        for domain in Domain:
            assert domain in results

    @pytest.mark.asyncio
    async def test_returns_results_per_domain(self, vector_store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["Content"]],
            "metadatas": [[{"doc_id": "doc1", "title": "Doc", "source": "/doc.md"}]],
            "distances": [[0.1]]
        }

        results = await vector_store.search_all("query")

        for domain in Domain:
            assert isinstance(results[domain], list)


class TestDomainEnum:
    def test_domain_has_all_expected_values(self):
        expected_domains = ["hr", "it", "finance", "legal", "marketing", "general"]

        for expected in expected_domains:
            assert expected in [d.value for d in Domain]

    def test_domain_is_string_enum(self):
        assert Domain.HR.value == "hr"
        assert str(Domain.HR) == "Domain.HR"


class TestSearchResult:
    def test_search_result_attributes(self):
        result = SearchResult(
            text="Test content",
            doc_id="doc123",
            title="Test Document",
            score=0.95,
            source="/path/to/doc.md",
            domain=Domain.HR
        )

        assert result.text == "Test content"
        assert result.doc_id == "doc123"
        assert result.title == "Test Document"
        assert result.score == 0.95
        assert result.source == "/path/to/doc.md"
        assert result.domain == Domain.HR
