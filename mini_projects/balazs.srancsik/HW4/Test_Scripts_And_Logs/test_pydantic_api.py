"""
Pydantic API Tests for SupportAI Application
Tests API endpoints, request/response validation, and data models
Generates HTML report with test results
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ValidationError, validator


class TestResults:
    """Class to store and generate HTML report for test results"""
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
        
    def add_result(self, test_name: str, status: str, message: str, duration: float, category: str = "General"):
        self.results.append({
            "test_name": test_name,
            "status": status,
            "message": message,
            "duration": duration,
            "category": category
        })
    
    def generate_html_report(self, output_path: str):
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        passed = sum(1 for r in self.results if r["status"] == "PASSED")
        failed = sum(1 for r in self.results if r["status"] == "FAILED")
        skipped = sum(1 for r in self.results if r["status"] == "SKIPPED")
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pydantic API Test Report - SupportAI</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #60a5fa; margin-bottom: 1rem; }}
        .summary {{ display: flex; gap: 2rem; margin-bottom: 2rem; padding: 1.5rem; background: #16213e; border-radius: 8px; }}
        .summary-item {{ text-align: center; }}
        .summary-item .value {{ font-size: 2rem; font-weight: bold; }}
        .summary-item .label {{ color: #888; font-size: 0.875rem; }}
        .passed {{ color: #4ade80; }}
        .failed {{ color: #f87171; }}
        .skipped {{ color: #fbbf24; }}
        .test-table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; margin-bottom: 2rem; }}
        .test-table th, .test-table td {{ padding: 1rem; text-align: left; border-bottom: 1px solid #2a2a4a; }}
        .test-table th {{ background: #0f3460; color: #60a5fa; }}
        .test-table tr:hover {{ background: #1a1a3e; }}
        .status-badge {{ padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }}
        .status-passed {{ background: #065f46; color: #4ade80; }}
        .status-failed {{ background: #7f1d1d; color: #f87171; }}
        .status-skipped {{ background: #78350f; color: #fbbf24; }}
        .meta {{ color: #888; font-size: 0.875rem; margin-bottom: 1rem; }}
        .category-header {{ background: #0f3460; padding: 0.75rem 1rem; margin: 1.5rem 0 0.5rem 0; border-radius: 4px; color: #FFD94F; font-weight: bold; }}
        .endpoint {{ font-family: monospace; background: #2a2a4a; padding: 0.25rem 0.5rem; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔌 Pydantic API Test Report</h1>
        <p class="meta">Generated: {end_time.strftime('%Y-%m-%d %H:%M:%S')} | Total Duration: {total_duration:.2f}s | Base URL: http://localhost:8000</p>
        
        <div class="summary">
            <div class="summary-item">
                <div class="value">{len(self.results)}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-item">
                <div class="value passed">{passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-item">
                <div class="value failed">{failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-item">
                <div class="value skipped">{skipped}</div>
                <div class="label">Skipped</div>
            </div>
        </div>
        
        <table class="test-table">
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Message</th>
                </tr>
            </thead>
            <tbody>
"""
        for result in self.results:
            status_class = f"status-{result['status'].lower()}"
            html += f"""
                <tr>
                    <td>{result['category']}</td>
                    <td>{result['test_name']}</td>
                    <td><span class="status-badge {status_class}">{result['status']}</span></td>
                    <td>{result['duration']:.3f}s</td>
                    <td>{result['message']}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path


# Global test results collector
test_results = TestResults()

# Base URL for API
BASE_URL = "http://localhost:8000"


# ==================== Pydantic Models ====================

class ChatRequest(BaseModel):
    """Model for chat request validation"""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    
    @validator('message')
    def message_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()


class ChatResponse(BaseModel):
    """Model for chat response validation"""
    response: str
    session_id: str
    tools_used: Optional[List[str]] = []
    timestamp: Optional[str] = None


class TicketFilterRequest(BaseModel):
    """Model for ticket filter request"""
    ticket_number: Optional[str] = ""
    user_name: Optional[str] = ""
    sentiment: Optional[str] = ""
    contact_time: Optional[str] = ""
    issue_type: Optional[str] = ""
    potential_issue: Optional[str] = ""
    owning_team: Optional[str] = ""
    priority: Optional[str] = ""
    
    @validator('sentiment')
    def validate_sentiment(cls, v):
        if v and v not in ["", "positive", "neutral", "frustrated"]:
            raise ValueError('Invalid sentiment value')
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in ["", "P1", "P2", "P3"]:
            raise ValueError('Invalid priority value')
        return v
    
    @validator('issue_type')
    def validate_issue_type(cls, v):
        valid_types = ["", "Billing Issues", "Account Issues", "Technical Issues", "Feature Requests"]
        if v and v not in valid_types:
            raise ValueError('Invalid issue type')
        return v


class ProfileUpdateRequest(BaseModel):
    """Model for profile update request"""
    name: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class TicketCountResponse(BaseModel):
    """Model for ticket count response"""
    total: int = Field(..., ge=0)


# ==================== Test Functions ====================

def test_api_health():
    """Test API health/availability"""
    start = time.time()
    test_name = "API Health Check"
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            test_results.add_result(test_name, "PASSED", f"API is healthy (status: {response.status_code})", duration, "Health")
        else:
            # Try alternative endpoint
            response = requests.get(f"{BASE_URL}/docs", timeout=10)
            if response.status_code == 200:
                test_results.add_result(test_name, "PASSED", "API docs accessible", duration, "Health")
            else:
                test_results.add_result(test_name, "FAILED", f"Unexpected status: {response.status_code}", duration, "Health")
    except requests.exceptions.ConnectionError:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", "Cannot connect to API server", duration, "Health")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Health")


def test_tickets_page_endpoint():
    """Test tickets page endpoint"""
    start = time.time()
    test_name = "Tickets Page Endpoint"
    try:
        response = requests.get(f"{BASE_URL}/tickets", timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            # Check if HTML content
            if "text/html" in response.headers.get("content-type", ""):
                test_results.add_result(test_name, "PASSED", "Tickets page returns HTML", duration, "Endpoints")
            else:
                test_results.add_result(test_name, "PASSED", f"Tickets page accessible (status: {response.status_code})", duration, "Endpoints")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Endpoints")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Endpoints")


def test_tickets_count_endpoint():
    """Test tickets count API endpoint"""
    start = time.time()
    test_name = "Tickets Count Endpoint"
    try:
        response = requests.get(f"{BASE_URL}/api/tickets/count", timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            # Validate with Pydantic
            count_response = TicketCountResponse(**data)
            test_results.add_result(test_name, "PASSED", f"Total tickets: {count_response.total}", duration, "Endpoints")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Endpoints")
    except ValidationError as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", f"Validation error: {e}", duration, "Endpoints")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Endpoints")


def test_tickets_filter_endpoint():
    """Test tickets filter API endpoint"""
    start = time.time()
    test_name = "Tickets Filter Endpoint"
    try:
        response = requests.get(f"{BASE_URL}/api/tickets/filter", timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            test_results.add_result(test_name, "PASSED", "Filter endpoint returns data", duration, "Endpoints")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Endpoints")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Endpoints")


def test_tickets_filter_with_params():
    """Test tickets filter with parameters"""
    start = time.time()
    test_name = "Tickets Filter with Parameters"
    try:
        # Create valid filter request
        filter_request = TicketFilterRequest(
            sentiment="positive",
            priority="P1"
        )
        
        params = filter_request.dict(exclude_none=True)
        response = requests.get(f"{BASE_URL}/api/tickets/filter", params=params, timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            test_results.add_result(test_name, "PASSED", "Filter with params works", duration, "Endpoints")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Endpoints")
    except ValidationError as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", f"Validation error: {e}", duration, "Endpoints")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Endpoints")


def test_chat_request_validation():
    """Test ChatRequest Pydantic model validation"""
    start = time.time()
    test_name = "ChatRequest Model Validation"
    try:
        # Valid request
        valid_request = ChatRequest(message="Hello, I need help")
        assert valid_request.message == "Hello, I need help"
        
        # Test with session_id
        request_with_session = ChatRequest(
            message="Test message",
            session_id="test-123",
            user_id="user-456"
        )
        assert request_with_session.session_id == "test-123"
        
        duration = time.time() - start
        test_results.add_result(test_name, "PASSED", "ChatRequest validation works", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_chat_request_empty_message():
    """Test ChatRequest rejects empty message"""
    start = time.time()
    test_name = "ChatRequest Empty Message Rejection"
    try:
        # This should raise ValidationError
        try:
            invalid_request = ChatRequest(message="")
            test_results.add_result(test_name, "FAILED", "Should have rejected empty message", time.time() - start, "Pydantic Models")
        except ValidationError:
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Empty message correctly rejected", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_ticket_filter_request_validation():
    """Test TicketFilterRequest Pydantic model"""
    start = time.time()
    test_name = "TicketFilterRequest Validation"
    try:
        # Valid filter request
        valid_filter = TicketFilterRequest(
            sentiment="positive",
            priority="P1",
            issue_type="Billing Issues"
        )
        assert valid_filter.sentiment == "positive"
        assert valid_filter.priority == "P1"
        
        duration = time.time() - start
        test_results.add_result(test_name, "PASSED", "TicketFilterRequest validation works", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_ticket_filter_invalid_sentiment():
    """Test TicketFilterRequest rejects invalid sentiment"""
    start = time.time()
    test_name = "TicketFilterRequest Invalid Sentiment"
    try:
        try:
            invalid_filter = TicketFilterRequest(sentiment="invalid_sentiment")
            test_results.add_result(test_name, "FAILED", "Should have rejected invalid sentiment", time.time() - start, "Pydantic Models")
        except ValidationError:
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Invalid sentiment correctly rejected", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_ticket_filter_invalid_priority():
    """Test TicketFilterRequest rejects invalid priority"""
    start = time.time()
    test_name = "TicketFilterRequest Invalid Priority"
    try:
        try:
            invalid_filter = TicketFilterRequest(priority="P5")
            test_results.add_result(test_name, "FAILED", "Should have rejected invalid priority", time.time() - start, "Pydantic Models")
        except ValidationError:
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Invalid priority correctly rejected", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_chat_response_validation():
    """Test ChatResponse Pydantic model"""
    start = time.time()
    test_name = "ChatResponse Model Validation"
    try:
        valid_response = ChatResponse(
            response="I can help you with that.",
            session_id="session-123",
            tools_used=["weather_tool", "documents_tool"]
        )
        assert valid_response.response == "I can help you with that."
        assert len(valid_response.tools_used) == 2
        
        duration = time.time() - start
        test_results.add_result(test_name, "PASSED", "ChatResponse validation works", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_profile_update_request():
    """Test ProfileUpdateRequest Pydantic model"""
    start = time.time()
    test_name = "ProfileUpdateRequest Validation"
    try:
        valid_profile = ProfileUpdateRequest(
            name="John Doe",
            email="john@example.com",
            preferences={"theme": "dark", "language": "en"}
        )
        assert valid_profile.name == "John Doe"
        assert valid_profile.preferences["theme"] == "dark"
        
        duration = time.time() - start
        test_results.add_result(test_name, "PASSED", "ProfileUpdateRequest validation works", duration, "Pydantic Models")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Pydantic Models")


def test_api_docs_endpoint():
    """Test API documentation endpoint"""
    start = time.time()
    test_name = "API Documentation Endpoint"
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            test_results.add_result(test_name, "PASSED", "API docs accessible at /docs", duration, "Documentation")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Documentation")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Documentation")


def test_openapi_schema():
    """Test OpenAPI schema endpoint"""
    start = time.time()
    test_name = "OpenAPI Schema Endpoint"
    try:
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            schema = response.json()
            if "openapi" in schema and "paths" in schema:
                test_results.add_result(test_name, "PASSED", f"OpenAPI version: {schema.get('openapi', 'unknown')}", duration, "Documentation")
            else:
                test_results.add_result(test_name, "FAILED", "Invalid OpenAPI schema", duration, "Documentation")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Documentation")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Documentation")


def test_session_endpoint():
    """Test session endpoint"""
    start = time.time()
    test_name = "Session Endpoint"
    try:
        response = requests.get(f"{BASE_URL}/api/session", timeout=10)
        duration = time.time() - start
        
        if response.status_code in [200, 404]:
            test_results.add_result(test_name, "PASSED", f"Session endpoint responded (status: {response.status_code})", duration, "Endpoints")
        else:
            test_results.add_result(test_name, "FAILED", f"Status: {response.status_code}", duration, "Endpoints")
    except Exception as e:
        duration = time.time() - start
        test_results.add_result(test_name, "FAILED", str(e), duration, "Endpoints")


def run_all_tests():
    """Run all API tests and generate HTML report"""
    print("=" * 60)
    print("Running Pydantic API Tests for SupportAI")
    print("=" * 60)
    
    # Health and Documentation tests
    test_api_health()
    test_api_docs_endpoint()
    test_openapi_schema()
    
    # Endpoint tests
    test_tickets_page_endpoint()
    test_tickets_count_endpoint()
    test_tickets_filter_endpoint()
    test_tickets_filter_with_params()
    test_session_endpoint()
    
    # Pydantic model validation tests
    test_chat_request_validation()
    test_chat_request_empty_message()
    test_chat_response_validation()
    test_ticket_filter_request_validation()
    test_ticket_filter_invalid_sentiment()
    test_ticket_filter_invalid_priority()
    test_profile_update_request()
    
    # Generate HTML report
    output_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(output_dir, "pydantic_api_test_report.html")
    test_results.generate_html_report(report_path)
    
    # Print summary
    passed = sum(1 for r in test_results.results if r["status"] == "PASSED")
    failed = sum(1 for r in test_results.results if r["status"] == "FAILED")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print(f"✅ HTML Report generated: {report_path}")
    print("=" * 60)
    
    return report_path


if __name__ == "__main__":
    run_all_tests()
