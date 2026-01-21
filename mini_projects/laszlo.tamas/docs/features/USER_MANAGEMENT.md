# User Management - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A user management rendszer multi-tenant user kezelést biztosít tenant-specific isolation-nel. Minden user egy tenant-hez tartozik, personalizált beállításokkal (nyelv, timezone, system prompt).

## Használat

### User információk lekérése
```python
from services.user_service import UserService

user_service = UserService()

# User context betöltés
user_context = await user_service.get_user_context(user_id=1, tenant_id=1)
print(f"User: {user_context.name}")
print(f"Language: {user_context.language}")
print(f"Timezone: {user_context.timezone}")

# User beállítások frissítés
await user_service.update_user_preferences(
    user_id=1,
    tenant_id=1,
    preferences={
        "language": "hu",
        "response_style": "detailed"
    }
)
```

### User authorization
```python
# User hozzáférés ellenőrzés
can_access = await user_service.validate_user_access(
    user_id=1,
    tenant_id=1,
    resource_type="document",
    resource_id=15
)
```

## Technikai implementáció

### User Service
```python
class UserService:
    def __init__(self):
        self.db = UserRepository()
        self.cache = UserContextCache()
    
    async def get_user_context(
        self, 
        user_id: int, 
        tenant_id: int
    ) -> UserContext:
        """Load complete user context with caching."""
        
        # Check cache first
        cached = await self.cache.get_user_context(user_id)
        if cached and cached.tenant_id == tenant_id:
            return cached
        
        # Load from database
        user_data = await self.db.get_user_with_tenant(user_id, tenant_id)
        if not user_data:
            raise UserNotFoundError(f"User {user_id} not found in tenant {tenant_id}")
        
        context = UserContext(
            user_id=user_data["user_id"],
            tenant_id=user_data["tenant_id"],
            name=f"{user_data['firstname']} {user_data['lastname']}",
            email=user_data["email"],
            language=user_data["default_lang"],
            timezone=user_data["timezone"],
            system_prompt=user_data["system_prompt"],
            tenant_system_prompt=user_data["tenant_system_prompt"],
            is_active=user_data["is_active"]
        )
        
        # Cache for future use
        await self.cache.set_user_context(user_id, context, ttl=600)
        
        return context

class UserRepository(TenantAwareRepository):
    async def get_user_with_tenant(
        self, 
        user_id: int, 
        tenant_id: int
    ) -> Optional[dict]:
        """Get user with tenant information."""
        
        query = """
        SELECT 
            u.user_id, u.tenant_id, u.firstname, u.lastname, u.nickname,
            u.email, u.role, u.is_active, u.default_lang, u.timezone,
            u.system_prompt, t.system_prompt as tenant_system_prompt
        FROM users u
        JOIN tenants t ON u.tenant_id = t.tenant_id
        WHERE u.user_id = %(user_id)s 
        AND u.is_active = true 
        AND t.is_active = true
        """
        
        result = await self.execute_tenant_query(query, tenant_id, {"user_id": user_id})
        return result[0] if result else None
    
    async def update_user_preferences(
        self,
        user_id: int,
        tenant_id: int,
        preferences: dict
    ):
        """Update user preferences with validation."""
        
        allowed_fields = {
            'default_lang', 'timezone', 'system_prompt'
        }
        
        update_fields = set(preferences.keys())
        if not update_fields.issubset(allowed_fields):
            raise ValidationError("Invalid preference fields")
        
        set_clauses = []
        params = {"user_id": user_id, "tenant_id": tenant_id}
        
        for field, value in preferences.items():
            set_clauses.append(f"{field} = %({field})s")
            params[field] = value
        
        query = f"""
        UPDATE users 
        SET {', '.join(set_clauses)}
        WHERE user_id = %(user_id)s AND tenant_id = %(tenant_id)s
        """
        
        await self.execute_tenant_query(query, tenant_id, params)
```

### User Authorization
```python
class UserAuthorizationService:
    async def validate_user_access(
        self,
        user_id: int,
        tenant_id: int,
        resource_type: str,
        resource_id: Optional[int] = None
    ) -> bool:
        """Validate user access to tenant resources."""
        
        # Check user belongs to tenant
        user = await self.user_service.get_user_context(user_id, tenant_id)
        if not user or not user.is_active:
            return False
        
        # Resource-specific checks
        if resource_type == "document" and resource_id:
            return await self._validate_document_access(
                user_id, tenant_id, resource_id
            )
        
        return True
    
    async def _validate_document_access(
        self,
        user_id: int,
        tenant_id: int,
        document_id: int
    ) -> bool:
        """Check document access based on visibility rules."""
        
        query = """
        SELECT visibility, user_id FROM documents 
        WHERE id = %(document_id)s AND tenant_id = %(tenant_id)s
        """
        
        result = await self.db.execute_tenant_query(
            query, tenant_id, {"document_id": document_id}
        )
        
        if not result:
            return False
        
        doc = result[0]
        
        # Tenant documents accessible to all tenant users
        if doc["visibility"] == "tenant":
            return True
        
        # Private documents only accessible to owner
        if doc["visibility"] == "private":
            return doc["user_id"] == user_id
        
        return False
```

## Funkció-specifikus konfiguráció

```ini
# User management
MAX_USERS_PER_TENANT=1000
USER_CONTEXT_CACHE_TTL_SEC=600
ENABLE_USER_PREFERENCES=true

# Authorization
ENABLE_DOCUMENT_VISIBILITY=true
AUDIT_USER_ACCESS=true
DEFAULT_USER_LANGUAGE=hu
```

### User Context Caching
```python
class UserContextCache:
    async def get_user_context(self, user_id: int) -> Optional[UserContext]:
        data = await redis_client.get(f"user_context:{user_id}")
        return UserContext.parse_raw(data) if data else None
    
    async def set_user_context(
        self, 
        user_id: int, 
        context: UserContext, 
        ttl: int = 600
    ):
        await redis_client.setex(
            f"user_context:{user_id}", 
            ttl, 
            context.json()
        )
```