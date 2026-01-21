"""
API Endpoint Tester - Knowledge Router PROD

Tests all API endpoints for the Knowledge Router system.

Usage:
    python debug/test_api_endpoints.py

Created: 2026-01-11 (Project rename + API restructure)
"""

import requests
import json
from typing import Dict, List, Tuple
from datetime import datetime
import os

# Configuration
BASE_URL = "http://localhost:8000/api"
TEST_USER_ID = 1
TEST_TENANT_ID = 1
TEST_SESSION_ID = None  # Will be created during test
TEST_DOCUMENT_ID = None  # Will be created if needed

# Test results storage
results = {
    "passed": [],
    "failed": [],
    "skipped": []
}


def log(message: str, level: str = "INFO"):
    """Pretty log output with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "[INFO]", "SUCCESS": "[OK]", "ERROR": "[FAIL]", "WARNING": "[WARN]", "SKIP": "[SKIP]"}
    print(f"[{timestamp}] {symbols.get(level, '[INFO]')} {message}")


def test_endpoint(
    method: str,
    endpoint: str,
    data: Dict = None,
    params: Dict = None,
    files: Dict = None,
    expected_status: List[int] = None,
    skip: bool = False,
    skip_reason: str = ""
) -> Tuple[bool, str]:
    """
    Test a single API endpoint
    
    Returns:
        (success: bool, message: str)
    """
    if skip:
        results["skipped"].append(endpoint)
        log(f"SKIP {method} {endpoint} - {skip_reason}", "SKIP")
        return True, f"Skipped: {skip_reason}"
    
    if expected_status is None:
        expected_status = [200, 201]
    
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            if files:
                response = requests.post(url, data=data, files=files, params=params)
            else:
                response = requests.post(url, json=data, params=params)
        elif method == "PATCH":
            response = requests.patch(url, json=data, params=params)
        elif method == "DELETE":
            response = requests.delete(url, params=params)
        else:
            return False, f"Unknown method: {method}"
        
        # Check status code
        if response.status_code not in expected_status:
            results["failed"].append(endpoint)
            log(f"{method} {endpoint} - FAILED: Status {response.status_code} (expected {expected_status})", "ERROR")
            return False, f"Status {response.status_code} (expected {expected_status})"
        
        results["passed"].append(endpoint)
        log(f"{method} {endpoint} - OK (Status {response.status_code})", "SUCCESS")
        return True, f"Status {response.status_code}"
    
    except Exception as e:
        results["failed"].append(endpoint)
        log(f"{method} {endpoint} - FAILED: {str(e)}", "ERROR")
        return False, str(e)


def run_tests():
    """Run all API endpoint tests"""
    global TEST_SESSION_ID, TEST_DOCUMENT_ID
    
    log("=" * 80, "INFO")
    log("Knowledge Router PROD - API Endpoint Testing", "INFO")
    log("=" * 80, "INFO")
    
    # ===== 0. SETUP: Ensure test document exists =====
    log("\nSetup: Checking for test document...", "INFO")
    
    # Check if documents exist
    try:
        response = requests.get(f"{BASE_URL}/documents/", params={
            "user_id": TEST_USER_ID,
            "tenant_id": TEST_TENANT_ID
        })
        
        if response.status_code == 200:
            documents_data = response.json()
            
            # Extract documents list from response
            documents = documents_data.get("documents", [])
            if isinstance(documents, list) and len(documents) > 0:
                # Use existing document
                TEST_DOCUMENT_ID = documents[0]["id"]
                log(f"Using existing document ID: {TEST_DOCUMENT_ID}", "SUCCESS")
            else:
                # Try to upload test document from test_documents folder
                log("No documents found, uploading test document from test_documents folder...", "INFO")
                
                test_file_path = "/test_documents/test_doc.txt"
                if os.path.exists(test_file_path):
                    # Read the actual test file
                    with open(test_file_path, 'rb') as f:
                        test_content = f.read()
                    filename = "test_doc.txt"
                    content_type = "text/plain"
                    log(f"Using test file: {test_file_path}", "INFO")
                else:
                    # Fallback to generated content
                    test_content = b"Test document for API testing. This is sample content for testing purposes."
                    filename = "test_document.txt"
                    content_type = "text/plain"
                    log("Test file not found, using generated content", "WARNING")
                
                upload_response = requests.post(
                    f"{BASE_URL}/workflows/process-document",
                    data={
                        "tenant_id": str(TEST_TENANT_ID),
                        "user_id": str(TEST_USER_ID),
                        "visibility": "private",
                        "enable_streaming": "false"
                    },
                    files={"file": (filename, test_content, content_type)}
                )
                
                if upload_response.status_code == 201:
                    TEST_DOCUMENT_ID = upload_response.json().get("document_id")
                    log(f"Test document uploaded successfully: ID={TEST_DOCUMENT_ID}", "SUCCESS")
                else:
                    log(f"Failed to upload test document: {upload_response.status_code}", "WARNING")
                    log("Document-dependent tests will be skipped", "WARNING")
        else:
            log(f"Failed to check documents: {response.status_code}", "WARNING")
            log("Document-dependent tests will be skipped", "WARNING")
    
    except Exception as e:
        log(f"Setup error: {str(e)}", "ERROR")
        log("Document-dependent tests will be skipped", "WARNING")
    
    # ===== 1. HEALTH & VERSION =====
    log("\nCategory: HEALTH & VERSION (2 endpoints)", "INFO")
    
    test_endpoint("GET", "/../health", expected_status=[200])  # Root level
    test_endpoint("GET", "/version")
    
    # ===== 2. TENANT ENDPOINTS =====
    log("\nCategory: TENANTS (3 endpoints)", "INFO")
    
    test_endpoint("GET", "/tenants", params={"active_only": "true"})
    test_endpoint("GET", "/tenants", params={"active_only": "false"})
    test_endpoint("PATCH", "/tenants/1", data={"system_prompt": "Test prompt"})
    
    # ===== 3. USER ENDPOINTS =====
    log("\nCategory: USERS (5 endpoints)", "INFO")
    
    test_endpoint("GET", "/tenants/1/users")
    test_endpoint("PATCH", "/users/1", data={"system_prompt": "User test"})
    
    # NEW user sub-resources
    test_endpoint("GET", f"/users/{TEST_USER_ID}/debug")
    test_endpoint("GET", f"/users/{TEST_USER_ID}/memories", params={"limit": 10})
    test_endpoint("DELETE", f"/users/{TEST_USER_ID}/conversations", expected_status=[200])
    
    # ===== 4. SESSION ENDPOINTS =====
    log("\nCategory: SESSIONS (5 endpoints)", "INFO")
    
    # Create session via chat endpoint (sessions are auto-created)
    log("Creating test session via /chat endpoint...", "INFO")
    response = requests.post(f"{BASE_URL}/chat", json={
        "user_id": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "query": "Test message to create session"
    })
    if response.status_code == 200:
        TEST_SESSION_ID = response.json().get("session_id")
        log(f"Created test session: {TEST_SESSION_ID}", "SUCCESS")
        results["passed"].append("/chat [session creation]")
    else:
        log(f"Failed to create test session: {response.status_code}", "ERROR")
        log("Skipping session-dependent tests", "WARNING")
        TEST_SESSION_ID = "test-session-id"  # Continue with tests
    
    test_endpoint("GET", "/sessions", params={"user_id": TEST_USER_ID})
    
    if TEST_SESSION_ID:
        # FIX: Add user_id query param to GET messages endpoint
        test_endpoint("GET", f"/sessions/{TEST_SESSION_ID}/messages", params={"user_id": TEST_USER_ID})
        test_endpoint("POST", f"/sessions/{TEST_SESSION_ID}/messages", data={
            "tenant_id": TEST_TENANT_ID,
            "user_id": TEST_USER_ID,
            "role": "system",
            "content": "Test system message"
        })
        test_endpoint("PATCH", f"/sessions/{TEST_SESSION_ID}/title", data={"title": "Test Session"})
        test_endpoint("DELETE", f"/sessions/{TEST_SESSION_ID}", expected_status=[200])
    
    # ===== 5. CHAT ENDPOINT =====
    log("\nCategory: CHAT (1 endpoint)", "INFO")
    
    test_endpoint("POST", "/chat", data={
        "user_id": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "query": "Hello, this is a test"
    })
    
    # ===== 6. DOCUMENT ENDPOINTS =====
    log("\nCategory: DOCUMENTS (3 endpoints)", "INFO")
    
    test_endpoint("GET", "/documents/", params={"user_id": TEST_USER_ID, "tenant_id": TEST_TENANT_ID})
    
    # Document detail/delete - use test document if available
    if TEST_DOCUMENT_ID:
        test_endpoint("GET", f"/documents/{TEST_DOCUMENT_ID}")
        test_endpoint("DELETE", f"/documents/{TEST_DOCUMENT_ID}")
    else:
        test_endpoint("GET", "/documents/1", skip=True, skip_reason="No test document available")
        test_endpoint("DELETE", "/documents/1", skip=True, skip_reason="No test document available")
    
    # ===== 7. RAG ENDPOINT =====
    log("\nCategory: RAG (1 endpoint)", "INFO")
    
    # FIX: RAG endpoint uses query params, not JSON body (+ user_id required)
    test_endpoint("POST", "/rag/retrieve", params={
        "query": "test query",
        "tenant_id": TEST_TENANT_ID,
        "user_id": TEST_USER_ID,
        "limit": 5
    })
    
    # ===== 8. WORKFLOW ENDPOINTS =====
    log("\nCategory: WORKFLOWS (2 endpoints)", "INFO")
    
    test_endpoint("GET", "/workflows/status")
    
    # Document upload via workflow
    log("Testing POST /workflows/process-document...", "INFO")
    test_content = b"Test document content for API testing"
    test_endpoint("POST", "/workflows/process-document", data={
        "tenant_id": str(TEST_TENANT_ID),
        "user_id": str(TEST_USER_ID),
        "visibility": "private",
        "enable_streaming": "false"
    }, files={
        "file": ("test_doc.txt", test_content, "text/plain")
    }, expected_status=[201, 200])
    
    # ===== 9. ADMIN ENDPOINTS =====
    log("\nCategory: ADMIN (6 endpoints)", "INFO")
    
    test_endpoint("GET", "/admin/cache/stats")
    test_endpoint("POST", "/admin/cache/enable", expected_status=[200, 400])
    test_endpoint("POST", "/admin/cache/disable", expected_status=[200, 400])
    test_endpoint("POST", "/admin/cache/clear")
    test_endpoint("DELETE", "/admin/cache/user/1")
    test_endpoint("DELETE", "/admin/cache/tenant/1")
    
    # ===== 10. DEBUG ENDPOINTS =====
    log("\nCategory: DEBUG (6 endpoints)", "INFO")
    
    test_endpoint("GET", "/db-check")
    test_endpoint("GET", f"/debug/{TEST_USER_ID}")
    test_endpoint("DELETE", f"/debug/{TEST_USER_ID}/conversations", expected_status=[200])
    test_endpoint("POST", "/debug/reset/postgres", expected_status=[200])
    test_endpoint("POST", "/debug/reset/qdrant", expected_status=[200])
    test_endpoint("POST", "/debug/reset/cache", expected_status=[200])
    
    # ===== 11. CONFIG ENDPOINTS =====
    log("\nCategory: CONFIG (1 endpoint)", "INFO")
    
    test_endpoint("GET", "/config/dev-mode")
    
    # ===== 12. HOWTO ENDPOINTS =====
    log("\nCategory: HOWTO (2 endpoints)", "INFO")
    
    test_endpoint("GET", "/howto/files")
    # FIX: Add 400 to expected status codes (endpoint validates slug)
    test_endpoint("GET", "/howto/test", expected_status=[200, 400, 404])  # May not exist or invalid slug
    
    # ===== SUMMARY =====
    log("\n" + "=" * 80, "INFO")
    log("TEST SUMMARY", "INFO")
    log("=" * 80, "INFO")
    
    total_tests = len(results["passed"]) + len(results["failed"]) + len(results["skipped"])
    
    log(f"Total Tests: {total_tests}", "INFO")
    log(f"Passed: {len(results['passed'])}", "SUCCESS")
    log(f"Skipped: {len(results['skipped'])}", "SKIP")
    log(f"Failed: {len(results['failed'])}", "ERROR")
    
    if results["failed"]:
        log("\nFailed endpoints:", "ERROR")
        for endpoint in results["failed"]:
            log(f"  - {endpoint}", "ERROR")
    
    log("\n" + "=" * 80, "INFO")
    
    # Calculate success rate
    tested = len(results["passed"]) + len(results["failed"])
    success_rate = (len(results["passed"]) / tested * 100) if tested > 0 else 0
    
    log(f"Success Rate: {success_rate:.1f}% ({len(results['passed'])}/{tested})", 
        "SUCCESS" if success_rate >= 90 else "WARNING")
    
    return success_rate >= 90


if __name__ == "__main__":
    try:
        success = run_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n\nTest interrupted by user", "WARNING")
        exit(1)
    except Exception as e:
        log(f"\n\nFatal error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        exit(1)
