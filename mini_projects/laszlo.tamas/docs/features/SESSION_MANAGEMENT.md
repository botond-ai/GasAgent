# Session Management - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A session management folyamatos beszélgetéseket tesz lehetővé a user és az AI között. Automatikusan kezeli a session létrehozást, folytatást, és lezárást, megőrizve a context-et és előkészítve a session summarykat.

## Használat

### Session kezelés API-n keresztül
```python
# Új beszélgetés indítás (session_id = null)
response = requests.post("http://localhost:8000/api/chat/", json={
    "query": "Szia! Mi a távmunka szabályzat?",
    "user_context": {"tenant_id": 1, "user_id": 1}
    # session_id nincs megadva -> új session
})

session_id = response.json()["session_id"]

# Beszélgetés folytatás
response2 = requests.post("http://localhost:8000/api/chat/", json={
    "query": "És mennyi home office nap engedélyezett?", 
    "user_context": {"tenant_id": 1, "user_id": 1},
    "session_id": session_id  # Meglévő session folytatása
})
```

### Programmatic session management
```python
from services.session_service import SessionService

session_service = SessionService()

# Session létrehozás
session = await session_service.create_session(tenant_id=1, user_id=1)
print(f"Session ID: {session.id}")

# Session információk
session_info = await session_service.get_session_info(session.id)
print(f"Created: {session_info.created_at}")
print(f"Messages: {session_info.message_count}")

# Session lezárás és summary készítés
await session_service.end_session(session.id)
```

## Technikai implementáció

### Session Lifecycle Management

```python
class SessionService:
    def __init__(self):
        self.db = SessionRepository()
        self.memory_service = LongTermMemoryService()
    
    async def create_session(
        self, 
        tenant_id: int, 
        user_id: int
    ) -> ChatSession:
        """Create new chat session with proper initialization."""
        
        session_id = str(uuid.uuid4())
        
        session = ChatSession(
            id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
            processed_for_ltm=False,
            is_deleted=False
        )
        
        await self.db.create_session(session)
        
        # Initialize session context
        await self._initialize_session_context(session_id, user_id)
        
        return session
    
    async def resume_or_create_session(
        self,
        session_id: Optional[str],
        tenant_id: int,
        user_id: int
    ) -> ChatSession:
        """Resume existing session or create new one."""
        
        if session_id:
            session = await self.get_active_session(session_id, tenant_id, user_id)
            if session:
                await self._update_session_activity(session_id)
                return session
        
        # Create new session if resume failed
        return await self.create_session(tenant_id, user_id)
    
    async def end_session(self, session_id: str) -> bool:
        """End session and trigger long-term memory processing."""
        
        session = await self.db.get_session(session_id)
        if not session:
            return False
        
        # Mark session as ended
        await self.db.update_session(session_id, {
            "ended_at": datetime.utcnow()
        })
        
        # Create session summary for long-term memory
        await self._create_session_summary(session_id)
        
        return True
    
    async def _create_session_summary(self, session_id: str):
        """Create long-term memory summary from session."""
        
        session = await self.db.get_session(session_id)
        conversation = await self.db.get_session_messages(session_id)
        
        if len(conversation) >= config.MIN_MESSAGES_FOR_SUMMARY:
            summary = await self.memory_service.create_session_summary(
                session_id=session_id,
                user_id=session.user_id,
                tenant_id=session.tenant_id
            )
            
            if summary:
                await self.db.update_session(session_id, {
                    "processed_for_ltm": True
                })

class SessionRepository(TenantAwareRepository):
    async def get_active_sessions_for_user(
        self, 
        user_id: int, 
        tenant_id: int,
        limit: int = 10
    ) -> List[ChatSession]:
        """Get recent active sessions for user."""
        
        query = """
        SELECT * FROM chat_sessions 
        WHERE user_id = %(user_id)s 
        AND ended_at IS NULL 
        AND is_deleted = false
        ORDER BY last_message_at DESC 
        LIMIT %(limit)s
        """
        
        return await self.execute_tenant_query(
            query, tenant_id, 
            {"user_id": user_id, "limit": limit}
        )
    
    async def cleanup_inactive_sessions(self, hours_inactive: int = 24):
        """Clean up sessions inactive for specified hours."""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_inactive)
        
        # End inactive sessions
        query = """
        UPDATE chat_sessions 
        SET ended_at = NOW()
        WHERE last_message_at < %(cutoff_time)s 
        AND ended_at IS NULL
        RETURNING id, user_id, tenant_id
        """
        
        ended_sessions = await self.db.execute(query, {"cutoff_time": cutoff_time})
        
        # Process ended sessions for LTM
        for session in ended_sessions:
            await self._create_session_summary(session["id"])
```

### Session Context and History

```python
class SessionContextManager:
    async def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = 20
    ) -> List[ChatMessage]:
        """Get recent conversation history for context."""
        
        query = """
        SELECT message_id, role, content, created_at, metadata
        FROM chat_messages 
        WHERE session_id = %(session_id)s
        ORDER BY created_at DESC 
        LIMIT %(limit)s
        """
        
        messages = await self.db.execute(query, {
            "session_id": session_id, 
            "limit": limit
        })
        
        return [ChatMessage(**msg) for msg in reversed(messages)]
    
    async def add_message_to_session(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ):
        """Add message to session and update activity."""
        
        # Insert message
        query = """
        INSERT INTO chat_messages 
        (session_id, tenant_id, user_id, role, content, metadata, created_at)
        SELECT %(session_id)s, tenant_id, user_id, %(role)s, %(content)s, %(metadata)s, NOW()
        FROM chat_sessions 
        WHERE id = %(session_id)s
        """
        
        await self.db.execute(query, {
            "session_id": session_id,
            "role": role, 
            "content": content,
            "metadata": metadata or {}
        })
        
        # Update session activity
        await self._update_session_activity(session_id)
```

## Funkció-specifikus konfiguráció

### Session Configuration
```ini
# Session lifecycle
SESSION_TIMEOUT_HOURS=24
MAX_SESSIONS_PER_USER=20
MIN_MESSAGES_FOR_SUMMARY=4

# Session cleanup
CLEANUP_INACTIVE_SESSIONS=true
CLEANUP_INTERVAL_HOURS=6
ENABLE_SESSION_ARCHIVING=true

# Context management
MAX_CONTEXT_MESSAGES=20
ENABLE_SESSION_CACHING=true
SESSION_CACHE_TTL_SEC=1800
```

### Performance Features
```python
# Session caching for quick access
class SessionCache:
    async def get_cached_session(self, session_id: str) -> Optional[ChatSession]:
        return await redis_client.get(f"session:{session_id}")
    
    async def cache_session(self, session: ChatSession, ttl: int = 1800):
        await redis_client.setex(
            f"session:{session.id}", 
            ttl, 
            session.json()
        )

# Batch session operations
async def process_multiple_sessions(session_ids: List[str]):
    tasks = [end_session(sid) for sid in session_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```