"""
Test script to verify ServiceError handling works correctly.
"""

import requests
import json

def test_validation_error():
    """Test ValidationError through API"""
    response = requests.post(
        "http://localhost:8000/api/v1/chat", 
        json={}  # Empty JSON should trigger validation error
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response.status_code == 400

def test_not_found_error():
    """Test NotFoundError through document access"""
    response = requests.get(
        "http://localhost:8000/api/v1/documents/99999", 
        params={"user_id": 1, "tenant_id": 1}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response.status_code == 404

if __name__ == "__main__":
    print("Testing ValidationError...")
    test_validation_error()
    
    print("\nTesting NotFoundError...")  
    test_not_found_error()