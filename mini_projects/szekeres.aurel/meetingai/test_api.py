#!/usr/bin/env python3
from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Test health endpoint
print("Testing /health...")
response = client.get("/health")
print(f"Status: {response.status_code}")
print(f"Body: {response.json()}\n")

# Test /summarize endpoint
print("Testing /summarize...")
payload = {
    "transcript": "Meeting with the team. Discussed Q4 goals. John will handle the frontend. Sarah will handle the backend.",
    "title": "Q4 Planning",
    "date": "2025-12-09",
    "participants": ["John", "Sarah"]
}
response = client.post("/summarize", json=payload)
print(f"Status: {response.status_code}")
print(f"Body: {response.json()}\n")

# Test /extract_tasks endpoint
print("Testing /extract_tasks...")
payload = {
    "transcript": "Meeting with the team. Discussed Q4 goals. John will handle the frontend. Sarah will handle the backend.",
    "meeting_reference": "MTG-2025-12-09-001"
}
response = client.post("/extract_tasks", json=payload)
print(f"Status: {response.status_code}")
print(f"Body: {response.json()}")
