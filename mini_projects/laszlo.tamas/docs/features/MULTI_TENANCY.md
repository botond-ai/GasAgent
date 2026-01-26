# Multi-tenancy - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A multi-tenant rendszer biztosítja, hogy minden vállalat (tenant) adatai teljesen elszigeteltek legyenek. Minden dokumentum, chat session, és memória tenant-specifikus, biztosítva a teljes adatvédelmet és testreszabhatóságot.

## Használat

### Tenant-specifikus operációk
```python
# Minden API hívás tenant_id-t igényel
from services.chat_workflow_service import ChatWorkflowService

chat_service = ChatWorkflowService()

# ACME Corporation (tenant_id=1) felhasználója
result_acme = await chat_service.process_chat_query(
    query="Mi a szabályzat a távmunkáról?",
    tenant_id=1,  # ACME Corp
    user_id=1     # Alice Johnson
)

# TechCorp (tenant_id=2) felhasználója - teljesen külön adatok
result_techcorp = await chat_service.process_chat_query(
    query="Mi a szabályzat a távmunkáról?", 
    tenant_id=2,  # TechCorp
    user_id=3     # John Doe
)

# Eredmények különbözőek lesznek, tenant-specifikus dokumentumok alapján
```

### Tenant konfigurációk kezelése
```python
# Tenant-specifikus beállítások
from services.tenant_service import TenantService

tenant_service = TenantService()

# Tenant konfiguráció betöltése
tenant_config = await tenant_service.get_tenant_config(tenant_id=1)
print(f"Tenant: {tenant_config.name}")
print(f"System prompt: {tenant_config.system_prompt}")
print(f"Active: {tenant_config.is_active}")

# Tenant beállítások módosítása
await tenant_service.update_tenant_config(
    tenant_id=1,
    config={
        "system_prompt": "ACME Corporation assistant. Always cite company policies.",
        "default_language": "hu",
        "enable_memory_creation": True
    }
)
```

### Cross-tenant data validation
```python
# Biztonsági ellenőrzések minden művelethez
from services.security_service import TenantSecurityService

security = TenantSecurityService()

# Document hozzáférés ellenőrzés
can_access = await security.can_user_access_document(
    user_id=1,
    tenant_id=1,
    document_id=15
)

if not can_access:
    raise AuthorizationError("Cross-tenant access denied")
```

## Technikai implementáció

### Multi-tenant Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT REQUEST ROUTING                       │
│  • Tenant ID extraction from request                           │
│  • Route to tenant-specific data pipelines                     │
│  • Enforce tenant authorization checks                         │
│  • Apply tenant-specific configurations                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER ISOLATION                         │
│  • PostgreSQL: tenant_id in all table WHERE clauses           │
│  • Qdrant: tenant_id in all vector search filters             │
│  • Redis: tenant-prefixed keys for caching                    │
│  • File storage: tenant-specific directory structure          │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT-SPECIFIC PROCESSING                   │
│  • Custom system prompts per tenant                            │
│  • Tenant-specific document visibility rules                   │
│  • Isolated user management and sessions                       │
│  • Separate workflow execution contexts                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CROSS-TENANT SECURITY ENFORCEMENT           │
│  • Prevent data leakage between tenants                        │
│  • Audit all cross-tenant access attempts                      │
│  • Rate limiting per tenant                                    │
│  • Tenant-specific error handling and logging                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tenant Data Isolation

#### Database-level Isolation
```python
class TenantAwareRepository:
    """Base class for all repositories that enforces tenant isolation."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def _add_tenant_filter(self, query: str, tenant_id: int, params: dict) -> tuple:
        """Automatically add tenant_id filter to all queries."""
        
        if "WHERE" in query.upper():
            query += " AND tenant_id = %(tenant_id)s"
        else:
            query += " WHERE tenant_id = %(tenant_id)s"
        
        params["tenant_id"] = tenant_id
        return query, params
    
    async def execute_tenant_query(
        self, 
        query: str, 
        tenant_id: int, 
        params: dict = None
    ) -> List[dict]:
        """Execute query with automatic tenant filtering."""
        
        if params is None:
            params = {}
        
        # Add tenant filter to query
        filtered_query, filtered_params = self._add_tenant_filter(
            query, tenant_id, params
        )
        
        # Log query for security audit
        self._audit_tenant_query(filtered_query, tenant_id, filtered_params)
        
        return await self.db.execute(filtered_query, filtered_params)
    
    def _audit_tenant_query(self, query: str, tenant_id: int, params: dict):
        """Audit tenant-specific database queries."""
        
        # Log all tenant queries for security monitoring
        log_info(
            "Tenant database query",
            tenant_id=tenant_id,
            query_type=self._extract_query_type(query),
            table_accessed=self._extract_table_name(query)
        )

class DocumentRepository(TenantAwareRepository):
    async def get_documents(self, tenant_id: int, visibility: str = None) -> List[Document]:
        """Get documents for specific tenant with optional visibility filter."""
        
        query = "SELECT * FROM documents"
        params = {}
        
        if visibility:
            query += " WHERE visibility = %(visibility)s"
            params["visibility"] = visibility
        
        # Tenant filter automatically added by parent class
        return await self.execute_tenant_query(query, tenant_id, params)
    
    async def create_document(
        self, 
        tenant_id: int,
        title: str,
        content: str,
        user_id: int = None,
        visibility: str = "tenant"
    ) -> int:
        """Create document with tenant isolation."""
        
        query = """
        INSERT INTO documents (tenant_id, user_id, title, content, visibility, created_at)
        VALUES (%(tenant_id)s, %(user_id)s, %(title)s, %(content)s, %(visibility)s, NOW())
        RETURNING id
        """
        
        params = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "title": title,
            "content": content,
            "visibility": visibility
        }
        
        result = await self.db.execute(query, params)
        return result[0]["id"]
```

#### Vector Database Isolation
```python
class TenantAwareQdrantStore:
    def __init__(self):
        self.client = QdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY
        )
    
    async def search_tenant_documents(
        self,
        tenant_id: int,
        query_vector: List[float],
        collection_name: str = "document_chunks",
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[ScoredPoint]:
        """Search documents with strict tenant isolation."""
        
        # Tenant isolation filter - CRITICAL for security
        tenant_filter = Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]
        )
        
        search_results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=tenant_filter,  # Always required
            limit=limit,
            score_threshold=score_threshold
        )
        
        # Additional security: verify all results have correct tenant_id
        for result in search_results:
            if result.payload.get("tenant_id") != tenant_id:
                log_error(
                    "Tenant isolation breach detected in Qdrant search",
                    expected_tenant=tenant_id,
                    found_tenant=result.payload.get("tenant_id"),
                    point_id=result.id
                )
                # Remove compromised result
                search_results.remove(result)
        
        return search_results
    
    async def store_tenant_embedding(
        self,
        tenant_id: int,
        point_id: str,
        vector: List[float],
        payload: dict
    ) -> bool:
        """Store embedding with tenant metadata."""
        
        # Force tenant_id in payload for isolation
        payload["tenant_id"] = tenant_id
        
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )
        
        operation_result = await self.client.upsert(
            collection_name="document_chunks",
            points=[point]
        )
        
        return operation_result.status == UpdateStatus.COMPLETED
```

### Tenant Configuration Management

#### Tenant Service
```python
class TenantService:
    def __init__(self):
        self.db = TenantAwareRepository(get_db_connection())
        self.config_cache = TenantConfigCache()
    
    async def get_tenant_config(self, tenant_id: int) -> TenantConfig:
        """Get complete tenant configuration with caching."""
        
        # Check cache first
        cached_config = await self.config_cache.get(tenant_id)
        if cached_config:
            return cached_config
        
        # Load from database
        query = """
        SELECT 
            tenant_id, key, name, is_active, system_prompt, 
            created_at, updated_at
        FROM tenants 
        WHERE tenant_id = %(tenant_id)s AND is_active = true
        """
        
        result = await self.db.execute(query, {"tenant_id": tenant_id})
        
        if not result:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found or inactive")
        
        tenant_data = result[0]
        config = TenantConfig(
            tenant_id=tenant_data["tenant_id"],
            key=tenant_data["key"],
            name=tenant_data["name"],
            is_active=tenant_data["is_active"],
            system_prompt=tenant_data["system_prompt"],
            created_at=tenant_data["created_at"],
            updated_at=tenant_data["updated_at"]
        )
        
        # Cache for future use
        await self.config_cache.set(tenant_id, config, ttl=300)  # 5-minute cache
        
        return config
    
    async def update_tenant_config(
        self,
        tenant_id: int,
        config_updates: dict
    ) -> TenantConfig:
        """Update tenant configuration safely."""
        
        # Validate update fields
        allowed_fields = {
            'system_prompt', 'name', 'is_active'
        }
        
        update_fields = set(config_updates.keys())
        if not update_fields.issubset(allowed_fields):
            invalid_fields = update_fields - allowed_fields
            raise ValidationError(f"Invalid config fields: {invalid_fields}")
        
        # Build update query
        set_clauses = []
        params = {"tenant_id": tenant_id, "updated_at": datetime.utcnow()}
        
        for field, value in config_updates.items():
            set_clauses.append(f"{field} = %({field})s")
            params[field] = value
        
        query = f"""
        UPDATE tenants 
        SET {', '.join(set_clauses)}, updated_at = %(updated_at)s
        WHERE tenant_id = %(tenant_id)s
        RETURNING *
        """
        
        result = await self.db.execute(query, params)
        
        if not result:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        # Invalidate cache
        await self.config_cache.delete(tenant_id)
        
        # Return updated config
        return await self.get_tenant_config(tenant_id)
    
    async def create_tenant(
        self,
        key: str,
        name: str,
        system_prompt: str = None
    ) -> TenantConfig:
        """Create new tenant with default configuration."""
        
        # Validate tenant key uniqueness
        existing = await self._check_tenant_key_exists(key)
        if existing:
            raise TenantKeyExistsError(f"Tenant key '{key}' already exists")
        
        # Default system prompt
        if not system_prompt:
            system_prompt = f"You are an AI assistant for {name}. Be helpful and professional."
        
        query = """
        INSERT INTO tenants (key, name, system_prompt, is_active, created_at, updated_at)
        VALUES (%(key)s, %(name)s, %(system_prompt)s, true, NOW(), NOW())
        RETURNING tenant_id
        """
        
        result = await self.db.execute(query, {
            "key": key,
            "name": name,
            "system_prompt": system_prompt
        })
        
        tenant_id = result[0]["tenant_id"]
        
        # Initialize tenant-specific resources
        await self._initialize_tenant_resources(tenant_id)
        
        return await self.get_tenant_config(tenant_id)
```

### Security Enforcement

#### Cross-tenant Access Prevention
```python
class TenantSecurityService:
    def __init__(self):
        self.db = TenantAwareRepository(get_db_connection())
        self.audit_logger = SecurityAuditLogger()
    
    async def validate_tenant_access(
        self,
        user_id: int,
        tenant_id: int,
        resource_type: str,
        resource_id: Optional[int] = None
    ) -> bool:
        """Validate that user has access to tenant resource."""
        
        # Check user belongs to tenant
        user_tenant_query = """
        SELECT tenant_id FROM users 
        WHERE user_id = %(user_id)s AND is_active = true
        """
        
        result = await self.db.execute(user_tenant_query, {"user_id": user_id})
        
        if not result:
            await self.audit_logger.log_access_violation(
                user_id=user_id,
                tenant_id=tenant_id,
                violation_type="user_not_found",
                resource_type=resource_type,
                resource_id=resource_id
            )
            return False
        
        user_tenant_id = result[0]["tenant_id"]
        
        if user_tenant_id != tenant_id:
            await self.audit_logger.log_access_violation(
                user_id=user_id,
                tenant_id=tenant_id,
                violation_type="cross_tenant_access",
                resource_type=resource_type,
                resource_id=resource_id,
                actual_tenant_id=user_tenant_id
            )
            return False
        
        # Additional resource-specific validation
        if resource_id:
            resource_valid = await self._validate_resource_tenant_ownership(
                tenant_id, resource_type, resource_id
            )
            if not resource_valid:
                await self.audit_logger.log_access_violation(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    violation_type="resource_tenant_mismatch",
                    resource_type=resource_type,
                    resource_id=resource_id
                )
                return False
        
        return True
    
    async def _validate_resource_tenant_ownership(
        self,
        tenant_id: int,
        resource_type: str,
        resource_id: int
    ) -> bool:
        """Validate resource belongs to specified tenant."""
        
        resource_queries = {
            "document": "SELECT tenant_id FROM documents WHERE id = %(resource_id)s",
            "chat_session": "SELECT tenant_id FROM chat_sessions WHERE id = %(resource_id)s",
            "long_term_memory": "SELECT tenant_id FROM long_term_memories WHERE id = %(resource_id)s"
        }
        
        if resource_type not in resource_queries:
            log_warning(f"Unknown resource type for validation: {resource_type}")
            return False
        
        query = resource_queries[resource_type]
        result = await self.db.execute(query, {"resource_id": resource_id})
        
        if not result:
            return False
        
        resource_tenant_id = result[0]["tenant_id"]
        return resource_tenant_id == tenant_id

class SecurityAuditLogger:
    async def log_access_violation(
        self,
        user_id: int,
        tenant_id: int,
        violation_type: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        **kwargs
    ):
        """Log security violations for monitoring and alerting."""
        
        violation_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "tenant_id": tenant_id,
            "violation_type": violation_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "additional_data": kwargs
        }
        
        # Log to security audit table
        await self._store_security_event(violation_event)
        
        # Send alert for serious violations
        if violation_type in ["cross_tenant_access", "privilege_escalation"]:
            await self._send_security_alert(violation_event)
        
        # Log to application logger
        log_error(
            f"Security violation: {violation_type}",
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            **kwargs
        )
```

### Tenant-specific Customization

#### Custom Workflow Behavior
```python
class TenantCustomWorkflow:
    @staticmethod
    def apply_tenant_customization(
        workflow_state: dict,
        tenant_config: TenantConfig
    ) -> dict:
        """Apply tenant-specific customizations to workflow."""
        
        # Apply custom system prompt
        if tenant_config.system_prompt:
            workflow_state["tenant_system_prompt"] = tenant_config.system_prompt
        
        # Tenant-specific processing rules
        tenant_rules = {
            1: {  # ACME Corporation
                "require_citations": True,
                "response_style": "formal",
                "max_response_length": 1000,
                "enable_memory_creation": True
            },
            2: {  # TechCorp
                "require_citations": False,
                "response_style": "casual",
                "max_response_length": 500,
                "enable_memory_creation": False
            }
        }
        
        rules = tenant_rules.get(tenant_config.tenant_id, {})
        workflow_state.update({
            f"tenant_{key}": value 
            for key, value in rules.items()
        })
        
        return workflow_state

class TenantSpecificPromptBuilder:
    @staticmethod
    def build_hierarchical_prompt(
        base_prompt: str,
        tenant_config: TenantConfig,
        user_context: UserContext
    ) -> str:
        """Build hierarchical prompt: base → tenant → user."""
        
        prompt_parts = [base_prompt]
        
        # Add tenant-specific prompt
        if tenant_config.system_prompt:
            prompt_parts.append(f"\nTenant Context ({tenant_config.name}):")
            prompt_parts.append(tenant_config.system_prompt)
        
        # Add user-specific prompt
        if user_context.system_prompt:
            prompt_parts.append(f"\nUser Context ({user_context.name}):")
            prompt_parts.append(user_context.system_prompt)
        
        # Add tenant-specific language and timezone
        prompt_parts.append(f"\nUser Language: {user_context.language}")
        prompt_parts.append(f"User Timezone: {user_context.timezone}")
        
        return "\n".join(prompt_parts)
```

## Funkció-specifikus konfiguráció

### Multi-tenant Security Configuration
```ini
# Tenant isolation enforcement
ENFORCE_TENANT_ISOLATION=true
AUDIT_CROSS_TENANT_ACCESS=true
BLOCK_SUSPICIOUS_QUERIES=true

# Tenant resource limits
MAX_DOCUMENTS_PER_TENANT=10000
MAX_USERS_PER_TENANT=1000
MAX_SESSIONS_PER_TENANT=50000

# Cache configuration
TENANT_CONFIG_CACHE_TTL_SEC=300
ENABLE_TENANT_CONFIG_CACHE=true
CACHE_PREFIX=tenant_config

# Security monitoring
ENABLE_SECURITY_AUDIT_LOGGING=true
ALERT_ON_CROSS_TENANT_ACCESS=true
MAX_FAILED_ACCESS_ATTEMPTS=5
```

### Tenant Data Partitioning
```python
# All services enforce tenant partitioning
class TenantAwareService:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.validate_tenant()
    
    def validate_tenant(self):
        """Validate tenant exists and is active."""
        if not self.tenant_id or self.tenant_id <= 0:
            raise InvalidTenantError("Invalid tenant ID")
    
    async def execute_operation(self, operation_func, *args, **kwargs):
        """Execute operation with tenant context."""
        
        # Add tenant_id to all operations
        kwargs["tenant_id"] = self.tenant_id
        
        # Execute with tenant isolation
        return await operation_func(*args, **kwargs)

# Example usage in all services
class ChatService(TenantAwareService):
    async def process_query(self, query: str, user_id: int):
        # tenant_id automatically included from parent class
        return await self.execute_operation(
            self._internal_process_query,
            query=query,
            user_id=user_id
        )
```

### Performance Monitoring per Tenant
```python
class TenantMetrics:
    @staticmethod
    def record_tenant_operation(
        tenant_id: int,
        operation: str,
        duration_ms: int,
        success: bool
    ):
        # Prometheus metrics with tenant labels
        prometheus_metrics.operation_duration.observe(
            duration_ms / 1000,
            labels={
                "tenant_id": str(tenant_id),
                "operation": operation,
                "status": "success" if success else "error"
            }
        )
        
        prometheus_metrics.tenant_operations_total.inc(
            labels={
                "tenant_id": str(tenant_id),
                "operation": operation
            }
        )
    
    @staticmethod
    def get_tenant_usage_stats(tenant_id: int) -> dict:
        """Get comprehensive tenant usage statistics."""
        return {
            "documents_count": count_tenant_documents(tenant_id),
            "users_count": count_tenant_users(tenant_id),
            "sessions_count": count_tenant_sessions(tenant_id),
            "memories_count": count_tenant_memories(tenant_id),
            "storage_mb": calculate_tenant_storage_usage(tenant_id),
            "last_activity": get_tenant_last_activity(tenant_id)
        }
```

### Tenant Migration and Management
```python
class TenantMigrationService:
    async def migrate_tenant_data(
        self,
        source_tenant_id: int,
        target_tenant_id: int,
        data_types: List[str]
    ):
        """Migrate specific data types between tenants (admin operation)."""
        
        migration_log = {
            "source_tenant": source_tenant_id,
            "target_tenant": target_tenant_id,
            "data_types": data_types,
            "started_at": datetime.utcnow(),
            "status": "in_progress"
        }
        
        try:
            for data_type in data_types:
                await self._migrate_data_type(
                    source_tenant_id, target_tenant_id, data_type
                )
            
            migration_log["status"] = "completed"
            migration_log["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            migration_log["status"] = "failed"
            migration_log["error"] = str(e)
            raise TenantMigrationError(f"Migration failed: {str(e)}")
        
        finally:
            await self._log_migration_result(migration_log)
    
    async def _migrate_data_type(
        self, 
        source_tenant: int, 
        target_tenant: int, 
        data_type: str
    ):
        """Migrate specific data type with proper tenant reassignment."""
        
        migration_handlers = {
            "documents": self._migrate_documents,
            "chat_sessions": self._migrate_chat_sessions,
            "long_term_memories": self._migrate_memories
        }
        
        if data_type not in migration_handlers:
            raise ValueError(f"Unknown data type: {data_type}")
        
        await migration_handlers[data_type](source_tenant, target_tenant)
```