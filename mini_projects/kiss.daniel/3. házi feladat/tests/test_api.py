"""Integration tests for the Flask API."""
import pytest
import json
from unittest.mock import patch, Mock


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    import sys
    import os
    
    # Add src to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    
    from api import app
    
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Test cases for /api/health endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'message' in data


class TestAskEndpoint:
    """Test cases for /api/ask endpoint."""
    
    @patch('api.run_agent')
    def test_ask_success(self, mock_run_agent, client):
        """Test successful question processing."""
        mock_run_agent.return_value = "Budapesten 15°C van, tiszta az ég."
        
        response = client.post(
            '/api/ask',
            data=json.dumps({'question': 'Milyen az időjárás Budapesten?'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['answer'] == "Budapesten 15°C van, tiszta az ég."
        
        mock_run_agent.assert_called_once_with('Milyen az időjárás Budapesten?')
    
    def test_ask_missing_question(self, client):
        """Test ask endpoint with missing question field."""
        response = client.post(
            '/api/ask',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'hiányzik' in data['error'].lower()
    
    def test_ask_empty_question(self, client):
        """Test ask endpoint with empty question."""
        response = client.post(
            '/api/ask',
            data=json.dumps({'question': '   '}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'üres' in data['error'].lower()
    
    def test_ask_invalid_json(self, client):
        """Test ask endpoint with invalid JSON."""
        response = client.post(
            '/api/ask',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code in [400, 500]
    
    @patch('api.run_agent')
    def test_ask_agent_error(self, mock_run_agent, client):
        """Test ask endpoint when agent raises error."""
        mock_run_agent.side_effect = Exception("Agent error")
        
        response = client.post(
            '/api/ask',
            data=json.dumps({'question': 'Test question'}),
            content_type='application/json'
        )
        
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'hiba' in data['error'].lower()
    
    @patch('api.run_agent')
    def test_ask_with_whitespace(self, mock_run_agent, client):
        """Test ask endpoint trims whitespace from question."""
        mock_run_agent.return_value = "Test answer"
        
        response = client.post(
            '/api/ask',
            data=json.dumps({'question': '  Test question  '}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        # Verify that whitespace was trimmed
        mock_run_agent.assert_called_once_with('Test question')
    
    def test_ask_no_content_type(self, client):
        """Test ask endpoint without content-type header."""
        response = client.post(
            '/api/ask',
            data=json.dumps({'question': 'Test'})
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 500]
    
    @patch('api.run_agent')
    def test_ask_cors_headers(self, mock_run_agent, client):
        """Test that CORS headers are present."""
        mock_run_agent.return_value = "Test answer"
        
        response = client.post(
            '/api/ask',
            data=json.dumps({'question': 'Test'}),
            content_type='application/json'
        )
        
        # CORS headers should be present
        assert 'Access-Control-Allow-Origin' in response.headers
    
    @patch('api.run_agent')
    def test_ask_multiple_questions(self, mock_run_agent, client):
        """Test multiple questions in sequence."""
        mock_run_agent.side_effect = [
            "Válasz 1",
            "Válasz 2",
            "Válasz 3"
        ]
        
        questions = [
            "Kérdés 1",
            "Kérdés 2",
            "Kérdés 3"
        ]
        
        for i, question in enumerate(questions):
            response = client.post(
                '/api/ask',
                data=json.dumps({'question': question}),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['answer'] == f"Válasz {i+1}"


class TestAPIMethods:
    """Test HTTP methods on endpoints."""
    
    def test_ask_get_method(self, client):
        """Test that GET is not allowed on /api/ask."""
        response = client.get('/api/ask')
        
        assert response.status_code == 405  # Method not allowed
    
    def test_health_post_method(self, client):
        """Test that POST works on /api/health (or returns 405)."""
        response = client.post('/api/health')
        
        # Either works or method not allowed
        assert response.status_code in [200, 405]
