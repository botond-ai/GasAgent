"""Tests for RAG agent and response caching."""
from __future__ import annotations

import tempfile
from pathlib import Path
import json

import pytest

from app.rag_agent import RAGAgent
from app.response_cache import ResponseCache


class TestResponseCache:
    def test_cache_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(tmpdir)
            query = "What happened?"
            docs = ["Document A", "Document B"]
            response = "This happened."

            cache.set(query, docs, response)
            cached = cache.get(query, docs)

            assert cached == response

    def test_cache_miss_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(tmpdir)
            cached = cache.get("nonexistent", ["doc1", "doc2"])
            assert cached is None

    def test_cache_key_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(tmpdir)
            query = "test"
            docs = ["a", "b", "c"]

            # Same query and docs (different order) should get same key
            key1 = cache._make_key(query, docs)
            key2 = cache._make_key(query, sorted(docs))
            assert key1 == key2

    def test_cache_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(tmpdir)
            cache.set("q1", ["d1"], "r1")
            cache.set("q2", ["d2"], "r2")

            cache_dir = Path(tmpdir)
            assert len(list(cache_dir.glob("*.json"))) == 2

            cache.clear()
            assert len(list(cache_dir.glob("*.json"))) == 0

    def test_cache_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(tmpdir)
            cache.set("q1", ["d1"], "r1")
            cache.set("q2", ["d2"], "r2")

            stats = cache.stats()
            assert stats["cache_entries"] == 2
            assert stats["cache_dir"] == tmpdir


class TestRAGAgent:
    def test_rag_agent_init(self):
        rag = RAGAgent(api_key="test-key", use_cache=False)
        assert rag.llm_model == "gpt-4o-mini"
        assert rag.temperature == 0.7
        assert rag.max_tokens == 1024
        assert rag.cache is None

    def test_rag_agent_with_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rag = RAGAgent(api_key="test-key", use_cache=True, cache_dir=tmpdir)
            assert rag.cache is not None

    def test_build_context_empty_docs(self):
        rag = RAGAgent(api_key="test-key", use_cache=False)
        context = rag._build_context([])
        assert "(No relevant documents found.)" in context

    def test_build_context_with_docs(self):
        rag = RAGAgent(api_key="test-key", use_cache=False)
        docs = [("id1", 0.95, "Text 1"), ("id2", 0.85, "Text 2")]
        context = rag._build_context(docs)

        assert "[Document 1 (relevance: 0.9500)]" in context
        assert "Text 1" in context
        assert "[Document 2 (relevance: 0.8500)]" in context
        assert "Text 2" in context


def test_cache_integration_with_rag(monkeypatch):
    """Test that RAG agent uses cache when available."""
    import app.rag_agent as rag_mod

    # Mock openai.ChatCompletion.create
    call_count = {"count": 0}

    def fake_create(**kwargs):
        call_count["count"] += 1
        return {
            "choices": [{"message": {"content": f"Response {call_count['count']}"}}]
        }

    monkeypatch.setattr(
        rag_mod, "openai", type("O", (), {"ChatCompletion": type("CC", (), {"create": staticmethod(fake_create)})})
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        rag = RAGAgent(api_key="test-key", use_cache=True, cache_dir=tmpdir)
        docs = [("id1", 0.9, "Text 1")]

        # First call should hit LLM
        resp1 = rag.generate_response("Question?", docs)
        assert call_count["count"] == 1
        assert "Response 1" in resp1

        # Second call with same query should hit cache
        resp2 = rag.generate_response("Question?", docs)
        assert call_count["count"] == 1  # No new API call
        assert "(cached)" in resp2

        # Different docs should trigger new API call
        resp3 = rag.generate_response("Question?", [("id2", 0.8, "Text 2")])
        assert call_count["count"] == 2
