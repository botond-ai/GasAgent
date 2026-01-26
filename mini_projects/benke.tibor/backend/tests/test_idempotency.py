"""
Unit tests for request idempotency (X-Request-ID header).

Tests Redis-based caching for duplicate requests to prevent
multiple LLM calls for the same request_id.
"""
import unittest
from unittest.mock import Mock, patch
import json
from rest_framework.test import APIRequestFactory
from rest_framework import status
from api.views import QueryAPIView


class TestIdempotency(unittest.TestCase):
    """Test request idempotency via X-Request-ID header."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = QueryAPIView.as_view()
        self.request_id = "test-request-123"
        
        # Mock query request data
        self.query_data = {
            "user_id": "test_user",
            "session_id": "test_session",
            "query": "What is the vacation policy?",
            "organisation": "Test Org"
        }
        
        # Mock response data
        self.mock_response_data = {
            "success": True,
            "data": {
                "domain": "hr",
                "answer": "Test answer",
                "citations": [],
                "workflow": None,
                "confidence": 0.95,
                "processing_status": "SUCCESS",
                "validation_errors": [],
                "retry_count": 0,
                "telemetry": {
                    "total_latency_ms": 1500.0,
                    "chunk_count": 3,
                    "max_similarity_score": 0.89
                }
            }
        }
    
    @patch('infrastructure.redis_client.redis_cache')
    @patch('django.apps.apps')
    def test_cache_miss_first_request(self, mock_apps, mock_redis):
        """Test first request with X-Request-ID performs full processing."""
        # Setup mocks
        mock_redis.get_request_response.return_value = None  # Cache MISS
        
        mock_chat_service = Mock()
        mock_response = Mock()
        mock_response.domain = "hr"
        mock_response.answer = "Test answer"
        mock_response.citations = []
        mock_response.workflow = None
        mock_response.confidence = 0.95
        mock_response.processing_status = Mock(value="SUCCESS")
        mock_response.validation_errors = []
        mock_response.retry_count = 0
        mock_response.rag_context = "test context"
        mock_response.llm_prompt = "test prompt"
        mock_response.llm_response = "test llm response"
        
        mock_chat_service.process_query = Mock(return_value=mock_response)
        
        mock_app = Mock()
        mock_app.chat_service = mock_chat_service
        mock_apps.get_app_config.return_value = mock_app
        
        # Make request with X-Request-ID
        request = self.factory.post(
            '/api/query/',
            data=json.dumps(self.query_data),
            content_type='application/json',
            HTTP_X_REQUEST_ID=self.request_id
        )
        
        # Simulate Django async run
        with patch('asyncio.run', side_effect=lambda coro: mock_response):
            response = self.view(request)
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify cache was checked
        mock_redis.get_request_response.assert_called_once_with(self.request_id)
        
        # Verify chat service was called (full processing)
        mock_chat_service.process_query.assert_called_once()
        
        # Verify response was cached
        mock_redis.set_request_response.assert_called_once()
        call_args = mock_redis.set_request_response.call_args
        self.assertEqual(call_args[0][0], self.request_id)  # request_id
        self.assertEqual(call_args[1]['ttl'], 300)  # 5 min TTL
    
    @patch('infrastructure.redis_client.redis_cache')
    def test_cache_hit_duplicate_request(self, mock_redis):
        """Test duplicate request with same X-Request-ID returns cached response."""
        # Setup cache HIT
        mock_redis.get_request_response.return_value = self.mock_response_data
        
        # Make request with same X-Request-ID
        request = self.factory.post(
            '/api/query/',
            data=json.dumps(self.query_data),
            content_type='application/json',
            HTTP_X_REQUEST_ID=self.request_id
        )
        
        response = self.view(request)
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify cache was checked
        mock_redis.get_request_response.assert_called_once_with(self.request_id)
        
        # Verify response is from cache
        self.assertEqual(response.data, self.mock_response_data)
        
        # Verify X-Cache-Hit header is set
        self.assertEqual(response['X-Cache-Hit'], 'true')
    
    @patch('infrastructure.redis_client.redis_cache')
    @patch('django.apps.apps')
    def test_different_request_ids_new_processing(self, mock_apps, mock_redis):
        """Test different request IDs trigger separate processing."""
        request_id_1 = "request-001"
        request_id_2 = "request-002"
        
        # Both cache MISS
        mock_redis.get_request_response.return_value = None
        
        mock_chat_service = Mock()
        mock_response = Mock()
        mock_response.domain = "hr"
        mock_response.answer = "Test answer"
        mock_response.citations = []
        mock_response.workflow = None
        mock_response.confidence = 0.95
        mock_response.processing_status = Mock(value="SUCCESS")
        mock_response.validation_errors = []
        mock_response.retry_count = 0
        mock_response.rag_context = "test"
        mock_response.llm_prompt = "test"
        mock_response.llm_response = "test"
        
        mock_chat_service.process_query = Mock(return_value=mock_response)
        
        mock_app = Mock()
        mock_app.chat_service = mock_chat_service
        mock_apps.get_app_config.return_value = mock_app
        
        # Request 1
        request1 = self.factory.post(
            '/api/query/',
            data=json.dumps(self.query_data),
            content_type='application/json',
            HTTP_X_REQUEST_ID=request_id_1
        )
        
        with patch('asyncio.run', side_effect=lambda coro: mock_response):
            response1 = self.view(request1)
        
        # Request 2
        request2 = self.factory.post(
            '/api/query/',
            data=json.dumps(self.query_data),
            content_type='application/json',
            HTTP_X_REQUEST_ID=request_id_2
        )
        
        with patch('asyncio.run', side_effect=lambda coro: mock_response):
            response2 = self.view(request2)
        
        # Both should succeed
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        # Both should check different cache keys
        calls = mock_redis.get_request_response.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], request_id_1)
        self.assertEqual(calls[1][0][0], request_id_2)
    
    @patch('infrastructure.redis_client.redis_cache')
    @patch('django.apps.apps')
    def test_no_request_id_normal_processing(self, mock_apps, mock_redis):
        """Test request without X-Request-ID performs normal processing (no caching)."""
        mock_chat_service = Mock()
        mock_response = Mock()
        mock_response.domain = "hr"
        mock_response.answer = "Test answer"
        mock_response.citations = []
        mock_response.workflow = None
        mock_response.confidence = 0.95
        mock_response.processing_status = Mock(value="SUCCESS")
        mock_response.validation_errors = []
        mock_response.retry_count = 0
        mock_response.rag_context = "test"
        mock_response.llm_prompt = "test"
        mock_response.llm_response = "test"
        
        mock_chat_service.process_query = Mock(return_value=mock_response)
        
        mock_app = Mock()
        mock_app.chat_service = mock_chat_service
        mock_apps.get_app_config.return_value = mock_app
        
        # Make request WITHOUT X-Request-ID header
        request = self.factory.post(
            '/api/query/',
            data=json.dumps(self.query_data),
            content_type='application/json'
        )
        
        with patch('asyncio.run', side_effect=lambda coro: mock_response):
            response = self.view(request)
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Cache should NOT be checked (no request_id)
        mock_redis.get_request_response.assert_not_called()
        
        # Cache should NOT be set (no request_id)
        mock_redis.set_request_response.assert_not_called()
    
    @patch('infrastructure.redis_client.redis_cache')
    @patch('django.apps.apps')
    def test_redis_unavailable_fallback(self, mock_apps, mock_redis):
        """Test graceful fallback when Redis is unavailable."""
        # Redis returns None (simulating unavailable cache)
        mock_redis.get_request_response.return_value = None
        
        mock_chat_service = Mock()
        mock_response = Mock()
        mock_response.domain = "hr"
        mock_response.answer = "Test answer"
        mock_response.citations = []
        mock_response.workflow = None
        mock_response.confidence = 0.95
        mock_response.processing_status = Mock(value="SUCCESS")
        mock_response.validation_errors = []
        mock_response.retry_count = 0
        mock_response.rag_context = "test"
        mock_response.llm_prompt = "test"
        mock_response.llm_response = "test"
        
        mock_chat_service.process_query = Mock(return_value=mock_response)
        
        mock_app = Mock()
        mock_app.chat_service = mock_chat_service
        mock_apps.get_app_config.return_value = mock_app
        
        request = self.factory.post(
            '/api/query/',
            data=json.dumps(self.query_data),
            content_type='application/json',
            HTTP_X_REQUEST_ID=self.request_id
        )
        
        with patch('asyncio.run', side_effect=lambda coro: mock_response):
            response = self.view(request)
        
        # Should still succeed (fallback to normal processing)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Chat service should be called (no cache)
        mock_chat_service.process_query.assert_called_once()


if __name__ == '__main__':
    unittest.main()
