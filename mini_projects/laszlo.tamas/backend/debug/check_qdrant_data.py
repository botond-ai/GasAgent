"""Check Qdrant collection contents."""

import os
import sys
sys.path.insert(0, '/app')

from qdrant_client import QdrantClient
from services.config_service import get_config_service

# Get dimensions from config
config = get_config_service()
VECTOR_DIMENSIONS = config.get_embedding_dimensions()

QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT_STR = os.getenv("QDRANT_PORT")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not all([QDRANT_HOST, QDRANT_PORT_STR, QDRANT_API_KEY]):
    raise ValueError("Qdrant configuration missing! Check .env file.")

QDRANT_PORT = int(QDRANT_PORT_STR)
COLLECTION_NAME = "r_d_ai_chat_document_chunks"

print("🔌 Connecting to Qdrant...")

protocol = "https"
url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"

client = QdrantClient(
    url=url,
    api_key=QDRANT_API_KEY
)

print(f"✅ Connected to: {url}")
print()

# Scroll through all points (get_collection has compatibility issues)
print("=== ALL POINTS ===")
points, _ = client.scroll(
    collection_name=COLLECTION_NAME,
    limit=100,
    with_payload=True,
    with_vectors=False
)

print(f"Retrieved {len(points)} points:")
print()

for i, point in enumerate(points, 1):
    print(f"Point #{i}")
    print(f"  ID: {point.id}")
    print(f"  Payload:")
    for key, value in point.payload.items():
        if key == "content_preview":
            print(f"    {key}: {value[:80]}...")
        else:
            print(f"    {key}: {value}")
    print()

# Search test
print("=== SEARCH TEST ===")
print("Creating a test query vector (zeros)...")

# Create a dummy query vector (same dimension as stored vectors)
test_vector = [0.0] * VECTOR_DIMENSIONS

search_results = client.search(
    collection_name=COLLECTION_NAME,
    query_vector=test_vector,
    limit=3,
    query_filter={
        "must": [
            {"key": "tenant_id", "match": {"value": 1}}
        ]
    }
)

print(f"Found {len(search_results)} results for tenant_id=1")
for i, hit in enumerate(search_results, 1):
    print(f"\nResult #{i}")
    print(f"  Score: {hit.score:.4f}")
    print(f"  Chunk ID: {hit.payload.get('chunk_id')}")
    print(f"  Document ID: {hit.payload.get('document_id')}")
    print(f"  Content preview: {hit.payload.get('content_preview', '')[:100]}...")

print("\n✅ Qdrant check complete!")
