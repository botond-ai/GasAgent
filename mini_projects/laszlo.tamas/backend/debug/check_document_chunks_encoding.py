"""Check encoding of chunks for a specific document."""

import sys
from database.pg_connection import get_db_connection

def check_document_chunks(document_id: int):
    """Check chunks for a document and verify encoding."""
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get document info
            cur.execute("""
                SELECT id, title, LENGTH(content) as content_len
                FROM documents
                WHERE id = %s
            """, (document_id,))
            
            doc = cur.fetchone()
            
            if not doc:
                print(f"❌ Document ID {document_id} not found!")
                return
            
            print(f"\n=== DOCUMENT INFO ===")
            print(f"ID: {doc['id']}")
            print(f"Title: {doc['title']}")
            print(f"Content Length: {doc['content_len']} chars")
            
            # Get chunks
            cur.execute("""
                SELECT 
                    id,
                    chunk_index,
                    start_offset,
                    end_offset,
                    LENGTH(content) as chunk_len,
                    content,
                    qdrant_point_id,
                    embedded_at
                FROM document_chunks
                WHERE document_id = %s
                ORDER BY chunk_index
            """, (document_id,))
            
            chunks = cur.fetchall()
            
            if not chunks:
                print(f"\n❌ No chunks found for document {document_id}")
                return
            
            print(f"\n=== CHUNKS ({len(chunks)} total) ===\n")
            
            for chunk in chunks:
                print(f"Chunk #{chunk['chunk_index']} (ID: {chunk['id']})")
                print(f"  Offset: {chunk['start_offset']} - {chunk['end_offset']}")
                print(f"  Length: {chunk['chunk_len']} chars")
                print(f"  Embedded: {'✅ Yes' if chunk['qdrant_point_id'] else '❌ No'}")
                
                # Check for Hungarian characters
                content = chunk['content']
                hungarian_chars = ['á', 'é', 'í', 'ó', 'ö', 'ő', 'ú', 'ü', 'ű', 'Á', 'É', 'Í', 'Ó', 'Ö', 'Ő', 'Ú', 'Ü', 'Ű']
                has_hungarian = any(char in content for char in hungarian_chars)
                
                print(f"  Hungarian chars: {'✅ Yes' if has_hungarian else '❌ No'}")
                
                # Show first 200 chars
                preview = content[:200].replace('\n', ' ')
                print(f"  Preview: {preview}...")
                
                # Try to decode/encode to check for encoding issues
                try:
                    # Check if there are any encoding issues
                    encoded = content.encode('utf-8')
                    decoded = encoded.decode('utf-8')
                    if content == decoded:
                        print(f"  Encoding: ✅ UTF-8 OK")
                    else:
                        print(f"  Encoding: ⚠️ Possible encoding mismatch")
                except UnicodeError as e:
                    print(f"  Encoding: ❌ ERROR - {e}")
                
                print()

if __name__ == "__main__":
    doc_id = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    check_document_chunks(doc_id)
