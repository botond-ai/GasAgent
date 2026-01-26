import sys
sys.path.insert(0, '/app')
from database.pg_init import get_session_messages_pg

session_id = '723ebfe1-55f4-4c23-9c44-4ca3496075a3'
messages = get_session_messages_pg(session_id, limit=100)

print('\n' + '='*80)
print(f'CHAT HISTORY FOR SESSION: {session_id}')
print('='*80 + '\n')
print(f'Total messages: {len(messages)}\n')

for idx, msg in enumerate(messages, 1):
    role = msg.get('role', 'unknown')
    content = msg.get('content', '')
    created = msg.get('created_at', 'unknown')
    
    print('-'*80)
    print(f'Message #{idx} - {role.upper()} - {created}')
    print('-'*80)
    print(content)
    print()
