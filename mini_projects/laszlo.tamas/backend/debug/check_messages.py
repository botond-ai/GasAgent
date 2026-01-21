"""Check messages in database."""
import sys
sys.path.insert(0, '/app')

from database.pg_connection import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Total messages
        cur.execute("SELECT COUNT(*) as cnt FROM chat_messages")
        total = cur.fetchone()['cnt']
        print(f"Total messages in chat_messages: {total}")
        
        # By user
        cur.execute("SELECT user_id, COUNT(*) as cnt FROM chat_messages GROUP BY user_id ORDER BY user_id")
        rows = cur.fetchall()
        print("\nMessages by user:")
        for r in rows:
            print(f"  User {r['user_id']}: {r['cnt']}")
        
        # Sample messages for user 1
        cur.execute("""
            SELECT message_id, role, LEFT(content, 50) as content_preview, created_at
            FROM chat_messages
            WHERE user_id = 1
            ORDER BY created_at DESC
            LIMIT 5
        """)
        msgs = cur.fetchall()
        print(f"\nLast 5 messages for user_id=1 ({len(msgs)} found):")
        for m in msgs:
            print(f"  [{m['created_at']}] {m['role']}: {m['content_preview']}...")
