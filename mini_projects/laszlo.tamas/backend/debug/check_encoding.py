"""Check message encoding in database."""
import sys
sys.path.insert(0, '/app')

from database.pg_init import get_last_messages_for_user_pg

# Updated: tenant_id parameter now required for security
msgs = get_last_messages_for_user_pg(user_id=1, tenant_id=1, limit=5)

print("Messages from database:")
print("=" * 80)
for i, m in enumerate(msgs, 1):
    print(f"\n{i}. [{m['role']}]")
    print(f"   Content: {m['content'][:150]}")
    print(f"   Encoding check: {repr(m['content'][:50])}")
