"""Check document by ID."""

import sys
from database.pg_connection import get_db_connection

doc_id = int(sys.argv[1]) if len(sys.argv) > 1 else 8

with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, LENGTH(content) as content_len, content
            FROM documents
            WHERE id = %s
        """, (doc_id,))
        
        row = cur.fetchone()
        
        if not row:
            print(f"❌ Document ID {doc_id} not found!")
        else:
            print(f"\n=== DOCUMENT {doc_id} ===")
            print(f"ID: {row['id']}")
            print(f"Title: {row['title']}")
            print(f"Content Length: {row['content_len']} chars")
            print()
            
            content = row['content']
            
            # Check encoding
            hungarian_chars = ['á', 'é', 'í', 'ó', 'ö', 'ő', 'ú', 'ü', 'ű', 
                             'Á', 'É', 'Í', 'Ó', 'Ö', 'Ő', 'Ú', 'Ü', 'Ű']
            has_hungarian = any(char in content for char in hungarian_chars)
            
            print(f"Has Hungarian characters: {'✅ YES' if has_hungarian else '❌ NO'}")
            print()
            
            # Show first 500 chars
            print("=== FIRST 500 CHARS ===")
            print(content[:500])
            print()
            
            # Count Hungarian chars
            hu_count = sum(1 for char in content if char in hungarian_chars)
            print(f"Total Hungarian chars: {hu_count}")
            
            # Estimate tokens (rough: 1 token ≈ 4 chars)
            estimated_tokens = row['content_len'] / 4
            print(f"Estimated tokens: ~{estimated_tokens:.0f}")
            
            # Expected chunks (from system.ini)
            from services.config_service import get_config_service
            config = get_config_service()
            chunk_size = config.get_chunk_size_tokens()
            overlap = config.get_chunk_overlap_tokens()
            expected_chunks = max(1, int(estimated_tokens / (chunk_size - overlap)) + 1)
            print(f"Expected chunks ({chunk_size} token, {overlap} overlap): ~{expected_chunks}")
