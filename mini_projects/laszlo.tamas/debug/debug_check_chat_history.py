"""
Check chat history for a specific session to verify what the LLM actually saw.
"""
import sys
import os

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from database.pg_init import get_session_messages_pg

def check_session_history(session_id: str):
    """Display all messages in a session."""
    print(f"\n{'='*80}")
    print(f"CHAT HISTORY FOR SESSION: {session_id}")
    print(f"{'='*80}\n")
    
    messages = get_session_messages_pg(session_id, limit=100)
    
    if not messages:
        print("❌ No messages found for this session!")
        return
    
    print(f"📊 Total messages: {len(messages)}\n")
    
    for idx, msg in enumerate(messages, 1):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        created = msg.get('created_at', 'unknown')
        
        print(f"{'-'*80}")
        print(f"Message #{idx} - {role.upper()} - {created}")
        print(f"{'-'*80}")
        print(f"{content[:500]}...")
        if len(content) > 500:
            print(f"[...{len(content) - 500} more characters...]")
        print()

if __name__ == "__main__":
    # Session ID from the user's example
    session_id = "723ebfe1-55f4-4c23-9c44-4ca3496075a3"
    
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
    
    check_session_history(session_id)
