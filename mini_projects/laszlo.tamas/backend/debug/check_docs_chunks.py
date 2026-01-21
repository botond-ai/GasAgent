"""Check documents and chunks in PostgreSQL."""
import sys
sys.path.insert(0, '/app')

from database.pg_connection import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Documents
        cur.execute("SELECT id, title, tenant_id, user_id FROM documents ORDER BY id")
        docs = cur.fetchall()
        print("Documents in PostgreSQL:")
        for d in docs:
            user_str = str(d.get('user_id')) if d.get('user_id') else 'NULL (tenant-wide)'
            print(f"  ID {d['id']}: {d['title']} (tenant={d['tenant_id']}, user={user_str})")
        
        # Chunks
        cur.execute("SELECT document_id, COUNT(*) as cnt FROM document_chunks GROUP BY document_id ORDER BY document_id")
        chunks = cur.fetchall()
        print("\nChunks by document:")
        for c in chunks:
            print(f"  Doc {c['document_id']}: {c['cnt']} chunks")
