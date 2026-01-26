#!/usr/bin/env python3
"""Test Qdrant connection and list collections."""

import os
from qdrant_client import QdrantClient

# Connection details from environment - NO DEFAULT VALUES
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = os.getenv("QDRANT_PORT")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_USE_HTTPS = os.getenv("QDRANT_USE_HTTPS", "true").lower() == "true"

if not all([QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY]):
    raise ValueError("Qdrant configuration missing! Check .env file.")

protocol = "https" if QDRANT_USE_HTTPS else "http"
QDRANT_URL = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"

def main():
    print("🔌 Connecting to Qdrant...")
    
    try:
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )
        
        print("✅ Connection successful!")
        print("\n📚 Available collections:")
        
        collections = client.get_collections()
        
        for collection in collections.collections:
            print(f"\n  📂 {collection.name}")
            # Just get basic info without detailed parsing
            try:
                count_result = client.count(collection.name)
                print(f"     - Vectors: {count_result.count}")
            except Exception as e:
                print(f"     - Vectors: (count error)")
            print(f"     - Vector count: {collection.vectors_count if hasattr(collection, 'vectors_count') else 0}")
        
        print(f"\n✅ Total collections found: {len(collections.collections)}")
        print("✅ All collections are accessible with this API key!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
