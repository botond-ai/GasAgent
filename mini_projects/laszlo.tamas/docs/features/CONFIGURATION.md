# Configuration - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A centralizált konfigurációs rendszer environment-alapú beállításokat biztosít minden komponenshez. Támogatja a runtime konfigurációs változtatásokat és tenant-specifikus customization-t.

## Használat

### Konfiguráció betöltése
```python
from config.settings import config

# Database settings
print(f"DB Host: {config.DATABASE_HOST}")
print(f"Max connections: {config.DATABASE_MAX_CONNECTIONS}")

# LLM settings  
print(f"OpenAI model: {config.OPENAI_MODEL}")
print(f"Max tokens: {config.MAX_TOKENS}")
```

### Environment-specific config
```bash
# Development
export ENVIRONMENT=development
export DEBUG=true
export LOG_LEVEL=DEBUG

# Production  
export ENVIRONMENT=production
export DEBUG=false
export LOG_LEVEL=INFO
```

## Technikai implementáció

### Configuration Manager
```python
class ConfigManager:
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self._load_config()
    
    def _load_config(self):
        # Database configuration
        self.DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
        self.DATABASE_PORT = int(os.getenv("DATABASE_PORT", "5432"))
        self.DATABASE_NAME = os.getenv("DATABASE_NAME", "k_r_")
        
        # LLM configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-11-20")
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))
        
        # Workflow configuration
        self.MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "5"))
        self.TOOL_EXECUTION_TIMEOUT_SEC = int(os.getenv("TOOL_EXECUTION_TIMEOUT_SEC", "30"))
        
        # Vector store configuration
        self.QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
        
        # Performance settings
        self.ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
        self.CACHE_TTL_SEC = int(os.getenv("CACHE_TTL_SEC", "300"))

# Global config instance
config = ConfigManager()
```

### Tenant-specific Configuration
```python
class TenantConfigManager:
    async def get_tenant_config(self, tenant_id: int) -> dict:
        """Get tenant-specific configuration overrides."""
        
        base_config = {
            "max_response_length": 1000,
            "enable_memory_creation": True,
            "response_style": "professional",
            "citation_required": True
        }
        
        # Load tenant overrides from database
        overrides = await self.db.get_tenant_config_overrides(tenant_id)
        
        return {**base_config, **overrides}
```

## Funkció-specifikus konfiguráció

### Environment Variables
```bash
# Core system
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=k_r_
DATABASE_MAX_CONNECTIONS=20

# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-2024-11-20
MAX_TOKENS=1000
LLM_TIMEOUT_SEC=30

# Vector store
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Performance
ENABLE_CACHING=true
CACHE_TTL_SEC=300
MAX_CONCURRENT_REQUESTS=100
```