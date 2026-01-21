"""Configuration service for system.ini."""

import os
import configparser
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for reading system.ini configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config service.
        
        Args:
            config_path: Path to system.ini file. If None, searches in backend directory.
        """
        if config_path is None:
            # Default: look for system.ini in backend/config directory
            backend_dir = Path(__file__).parent.parent
            config_path = backend_dir / "config" / "system.ini"
        
        self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()
        
        if not self.config_path.exists():
            logger.warning(f"system.ini not found at {self.config_path}, using defaults")
        else:
            self.config.read(self.config_path, encoding='utf-8')
            logger.info(f"Loaded system.ini from {self.config_path}")
    
    def get(self, section: str, key: str, default: str = "") -> str:
        """
        Get a string value from config.
        
        Args:
            section: Section name (e.g., 'rag', 'llm')
            key: Key name
            default: Default value if not found
        
        Returns:
            Configuration value as string
        """
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            logger.debug(f"Config {section}.{key} not found, using default: {default}")
            return default
    
    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """Get an integer value from config."""
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            logger.debug(f"Config {section}.{key} not found, using default: {default}")
            return default
    
    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """Get a float value from config."""
        try:
            return self.config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            logger.debug(f"Config {section}.{key} not found, using default: {default}")
            return default
    
    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Get a boolean value from config."""
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            logger.debug(f"Config {section}.{key} not found, using default: {default}")
            return default
    
    # === APPLICATION ===
    
    def get_system_prompt(self) -> str:
        """Get global system prompt."""
        return self.get('application', 'system_prompt', 
                       'Te egy hasznos AI asszisztens vagy.')
    
    def is_dev_mode(self) -> bool:
        """Check if development mode is enabled (disables all caches)."""
        return self.get_bool('development', 'DEV_MODE', False)
    
    def get_idle_timeout_seconds(self) -> int:
        """Get idle timeout for auto-consolidation (in seconds)."""
        return self.get_int('memory', 'IDLE_TIMEOUT_SECONDS', 300)
    
    # === RAG SETTINGS ===
    
    def get_chunking_strategy(self) -> str:
        """Get chunking strategy (e.g., 'recursive')."""
        return self.get('rag', 'CHUNKING_STRATEGY', 'recursive')
    
    def get_chunk_size_tokens(self) -> int:
        """Get chunk size in tokens."""
        return self.get_int('rag', 'CHUNK_SIZE_TOKENS', 500)
    
    def get_chunk_overlap_tokens(self) -> int:
        """Get chunk overlap in tokens."""
        return self.get_int('rag', 'CHUNK_OVERLAP_TOKENS', 50)
    
    def get_embedding_model(self) -> str:
        """Get embedding model name from environment variable."""
        model = os.getenv('OPENAI_MODEL_EMBEDDING')
        if not model:
            raise ValueError('OPENAI_MODEL_EMBEDDING must be set in .env file')
        return model
    
    def get_embedding_dimensions(self) -> int:
        """Get embedding vector dimensions."""
        return self.get_int('rag', 'EMBEDDING_DIMENSIONS', 3072)
    
    def get_embedding_batch_size(self) -> int:
        """Get max batch size for embedding API calls."""
        return self.get_int('rag', 'EMBEDDING_BATCH_SIZE', 100)
    
    def get_top_k_documents(self) -> int:
        """Get top-K documents to retrieve."""
        return self.get_int('rag', 'TOP_K_DOCUMENTS', 5)
    
    def get_min_score_threshold(self) -> float:
        """Get minimum similarity score threshold."""
        return self.get_float('rag', 'MIN_SCORE_THRESHOLD', 0.7)
    
    def get_qdrant_search_limit(self) -> int:
        """Get Qdrant search limit (max results to fetch)."""
        return self.get_int('rag', 'QDRANT_SEARCH_LIMIT', 10)
    
    def get_qdrant_search_offset(self) -> int:
        """Get Qdrant search offset."""
        return self.get_int('rag', 'QDRANT_SEARCH_OFFSET', 0)
    
    def get_qdrant_upload_batch_size(self) -> int:
        """Get Qdrant upload batch size (to avoid payload size limit)."""
        return self.get_int('rag', 'QDRANT_UPLOAD_BATCH_SIZE', 50)
    
    # === LLM SETTINGS ===
    
    def get_heavy_model(self) -> str:
        """Get heavy model name from environment variable (complex reasoning, content generation, RAG synthesis)."""
        model = os.getenv('OPENAI_MODEL_HEAVY')
        if not model:
            raise ValueError('OPENAI_MODEL_HEAVY must be set in .env file')
        return model
    
    def get_light_model(self) -> str:
        """Get light model name from environment variable (routing, extraction, tool selection)."""
        model = os.getenv('OPENAI_MODEL_LIGHT')
        if not model:
            raise ValueError('OPENAI_MODEL_LIGHT must be set in .env file')
        return model
    
    def get_medium_model(self) -> str:
        """Get medium model name from environment variable (standard RAG, balanced reasoning)."""
        model = os.getenv('OPENAI_MODEL_MEDIUM')
        if not model:
            raise ValueError('OPENAI_MODEL_MEDIUM must be set in .env file')
        return model
    
    # Backward compatibility (deprecated)
    def get_chat_model(self) -> str:
        """Deprecated: Use get_heavy_model() instead."""
        return self.get_heavy_model()
    
    def get_max_tokens(self) -> int:
        """Get max tokens for heavy model LLM response (backward compatibility - uses HEAVY_RAG context)."""
        return self.get_int('llm.contexts', 'HEAVY_RAG_MAX_TOKENS', 1500)
    
    def get_temperature(self) -> float:
        """Get temperature for heavy model LLM (backward compatibility - uses HEAVY_RAG context)."""
        return self.get_float('llm.contexts', 'HEAVY_RAG_TEMP', 0.2)
    
    def get_light_max_tokens(self) -> int:
        """Get max tokens for lightweight model (backward compatibility - uses LIGHT_CHAT context)."""
        return self.get_int('llm.contexts', 'LIGHT_CHAT_MAX_TOKENS', 500)
    
    def get_light_temperature(self) -> float:
        """Get temperature for lightweight model (backward compatibility - uses LIGHT_CHAT context)."""
        return self.get_float('llm.contexts', 'LIGHT_CHAT_TEMP', 0.7)
    
    # === LLM CONTEXT-SPECIFIC SETTINGS ===
    
    def get_light_chat_temperature(self) -> float:
        """Temperature for light model in chat context."""
        return self.get_float('llm.contexts', 'LIGHT_CHAT_TEMP', 0.7)
    
    def get_light_chat_max_tokens(self) -> int:
        """Max tokens for light model in chat context."""
        return self.get_int('llm.contexts', 'LIGHT_CHAT_MAX_TOKENS', 500)
    
    def get_light_router_temperature(self) -> float:
        """Temperature for light model in routing context (more deterministic)."""
        return self.get_float('llm.contexts', 'LIGHT_ROUTER_TEMP', 0.2)
    
    def get_light_router_max_tokens(self) -> int:
        """Max tokens for light model in routing context."""
        return self.get_int('llm.contexts', 'LIGHT_ROUTER_MAX_TOKENS', 300)
    
    # === MEDIUM MODEL CONTEXT SETTINGS ===
    
    def get_medium_chat_temperature(self) -> float:
        """Temperature for medium model in chat context."""
        return self.get_float('llm.contexts', 'MEDIUM_CHAT_TEMP', 0.5)
    
    def get_medium_chat_max_tokens(self) -> int:
        """Max tokens for medium model in chat context."""
        return self.get_int('llm.contexts', 'MEDIUM_CHAT_MAX_TOKENS', 800)
    
    def get_medium_rag_temperature(self) -> float:
        """Temperature for medium model in RAG synthesis context."""
        return self.get_float('llm.contexts', 'MEDIUM_RAG_TEMP', 0.3)
    
    def get_medium_rag_max_tokens(self) -> int:
        """Max tokens for medium model in RAG synthesis context."""
        return self.get_int('llm.contexts', 'MEDIUM_RAG_MAX_TOKENS', 1500)
    
    # === HEAVY MODEL CONTEXT SETTINGS ===
    
    def get_heavy_rag_temperature(self) -> float:
        """Temperature for heavy model in RAG synthesis context."""
        return self.get_float('llm.contexts', 'HEAVY_RAG_TEMP', 0.2)
    
    def get_heavy_rag_max_tokens(self) -> int:
        """Max tokens for heavy model in RAG synthesis context."""
        return self.get_int('llm.contexts', 'HEAVY_RAG_MAX_TOKENS', 1500)
    
    def get_heavy_big_think_temperature(self) -> float:
        """Temperature for heavy model in complex reasoning context."""
        return self.get_float('llm.contexts', 'HEAVY_BIG_THINK_TEMP', 0.1)
    
    def get_heavy_big_think_max_tokens(self) -> int:
        """Max tokens for heavy model in complex reasoning context."""
        return self.get_int('llm.contexts', 'HEAVY_BIG_THINK_MAX_TOKENS', 4000)

    def get_llm_max_completion_tokens(self) -> int:
        """Explicit max_completion_tokens to include in OpenAI payload."""
        return self.get_int('llm', 'MAX_COMPLETION_TOKENS', 0)

    # === MEMORY SETTINGS ===
    
    def is_longterm_chat_storage_enabled(self) -> bool:
        """Check if long-term chat memory storage is enabled."""
        return self.get_bool('memory', 'ENABLE_LONGTERM_CHAT_STORAGE', False)
    
    def is_longterm_chat_retrieval_enabled(self) -> bool:
        """Check if long-term chat memory retrieval is enabled."""
        return self.get_bool('memory', 'ENABLE_LONGTERM_CHAT_RETRIEVAL', False)
    
    def get_session_summary_max_tokens(self) -> int:
        """Get max tokens for session summary."""
        return self.get_int('memory', 'CHAT_SUMMARY_MAX_TOKENS', 200)
    
    def get_min_messages_for_consolidation(self) -> int:
        """Get minimum messages required for memory consolidation."""
        return self.get_int('memory', 'MIN_MESSAGES_FOR_CONSOLIDATION', 5)
    
    def get_consolidate_after_messages(self) -> int:
        """Get message threshold for consolidation trigger."""
        return self.get_int('memory', 'CONSOLIDATE_AFTER_MESSAGES', 50)
    
    def get_top_k_long_term_memories(self) -> int:
        """Get how many previous session summaries to retrieve."""
        return self.get_int('memory', 'TOP_K_LONG_TERM_MEMORIES', 3)
    
    def get_memory_score_threshold(self) -> float:
        """Get minimum similarity score for relevant memories."""
        return self.get_float('memory', 'MEMORY_SCORE_THRESHOLD', 0.5)
    
    # === LIMITS ===
    
    def get_max_file_size_mb(self) -> int:
        """Get max file upload size in MB."""
        return self.get_int('limits', 'MAX_FILE_SIZE_MB', 10)
    
    def get_max_chunks_per_document(self) -> int:
        """Get max chunks per document."""
        return self.get_int('limits', 'MAX_CHUNKS_PER_DOCUMENT', 1000)
    
    def get_max_documents_per_user(self) -> int:
        """Get max documents per user."""
        return self.get_int('limits', 'MAX_DOCUMENTS_PER_USER', 100)
    
    # === RESILIENCE SETTINGS ===
    
    def get_openai_timeout(self) -> float:
        """Get OpenAI API timeout in seconds."""
        return float(self.get_int('resilience', 'OPENAI_TIMEOUT_SECONDS', 60))
    
    def get_qdrant_timeout(self) -> float:
        """Get Qdrant API timeout in seconds."""
        return float(self.get_int('resilience', 'QDRANT_TIMEOUT_SECONDS', 30))
    
    def get_database_timeout(self) -> float:
        """Get database connection timeout in seconds."""
        return float(self.get_int('resilience', 'DATABASE_TIMEOUT_SECONDS', 30))
    
    def get_max_retries(self) -> int:
        """Get maximum retry attempts for transient failures."""
        return self.get_int('resilience', 'MAX_RETRIES', 3)
    
    def get_backoff_multiplier(self) -> float:
        """Get exponential backoff multiplier."""
        return self.get_float('resilience', 'BACKOFF_MULTIPLIER', 2.0)
    
    def get_initial_backoff(self) -> float:
        """Get initial backoff delay in seconds."""
        return float(self.get_int('resilience', 'INITIAL_BACKOFF_SECONDS', 1))
    
    def get_max_delay(self) -> float:
        """Get maximum delay cap in seconds."""
        return float(self.get_int('resilience', 'MAX_DELAY_SECONDS', 10))
    
    def get_rate_limit_max_attempts(self) -> int:
        """Get maximum retry attempts for rate limit errors."""
        return self.get_int('resilience', 'RATE_LIMIT_MAX_ATTEMPTS', 5)
    
    def get_rate_limit_initial_delay(self) -> float:
        """Get initial delay for rate limit retries in seconds."""
        return float(self.get_int('resilience', 'RATE_LIMIT_INITIAL_DELAY', 2))
    
    def get_rate_limit_max_delay(self) -> float:
        """Get maximum delay for rate limit retries in seconds."""
        return float(self.get_int('resilience', 'RATE_LIMIT_MAX_DELAY', 60))
    
    def get_rate_limit_multiplier(self) -> float:
        """Get exponential multiplier for rate limit retries."""
        return self.get_float('resilience', 'RATE_LIMIT_MULTIPLIER', 2.0)
    
    def get_quick_retry_max_attempts(self) -> int:
        """Get maximum retry attempts for quick operations."""
        return self.get_int('resilience', 'QUICK_RETRY_MAX_ATTEMPTS', 2)
    
    def get_quick_retry_initial_delay(self) -> float:
        """Get initial delay for quick retries in seconds."""
        return self.get_float('resilience', 'QUICK_RETRY_INITIAL_DELAY', 0.5)
    
    # === FEATURE FLAGS ===
    
    def get_query_rewrite_enabled(self) -> bool:
        """
        Check if query rewrite feature is enabled.
        
        Query rewrite performs LLM-based optimization of user queries before RAG search:
        - Pronoun resolution ("erről" → "Knowledge Router")
        - Keyword expansion for better semantic search
        - Context integration from chat history
        
        Can be overridden at runtime via request parameter for A/B testing.
        
        Cost: ~250-400ms latency, ~$0.0003 per request (light LLM)
        Benefit: +15-20% RAG precision improvement (estimated)
        
        Returns:
            True if enabled (default: True)
        """
        return self.get_bool('features', 'QUERY_REWRITE_ENABLED', True)


# Singleton instance
_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    """Get singleton config service instance."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
