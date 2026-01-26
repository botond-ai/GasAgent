"""
Unit Test: Config Service
Knowledge Router PROD

Tests ConfigService functionality:
- INI file loading
- Type conversions (string, int, float, bool)
- Default value fallbacks
- Environment variable overrides
- Specific config getters

Priority: HIGH (config is used everywhere)
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from tempfile import NamedTemporaryFile
from services.config_service import ConfigService


@pytest.mark.unit
class TestConfigService:
    """Test ConfigService functionality."""
    
    # ========================================================================
    # INI FILE LOADING
    # ========================================================================
    
    def test_load_from_file(self, tmp_path):
        """Test loading config from INI file."""
        config_content = """
[application]
system_prompt = Test prompt

[rag]
CHUNK_SIZE_TOKENS = 500
MIN_SCORE_THRESHOLD = 0.75

[development]
DEV_MODE = true
"""
        config_file = tmp_path / "test_system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.get('application', 'system_prompt') == "Test prompt"
        assert config.get_int('rag', 'CHUNK_SIZE_TOKENS') == 500
        assert config.get_float('rag', 'MIN_SCORE_THRESHOLD') == 0.75
        assert config.is_dev_mode() is True
    
    def test_missing_file_uses_defaults(self, tmp_path):
        """Test that missing config file doesn't crash, uses defaults."""
        config = ConfigService(config_path=str(tmp_path / "nonexistent.ini"))
        
        # Should return default values
        assert config.get('any', 'key', 'default_value') == 'default_value'
        assert config.get_int('any', 'key', 42) == 42
    
    # ========================================================================
    # TYPE CONVERSIONS
    # ========================================================================
    
    def test_get_string(self, tmp_path):
        """Test get() returns string values."""
        config_content = """
[test]
string_value = hello world
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        result = config.get('test', 'string_value')
        assert result == "hello world"
        assert isinstance(result, str)
    
    def test_get_int(self, tmp_path):
        """Test get_int() returns integer values."""
        config_content = """
[test]
int_value = 42
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        result = config.get_int('test', 'int_value')
        assert result == 42
        assert isinstance(result, int)
    
    def test_get_int_invalid_returns_default(self, tmp_path):
        """Test get_int() returns default for invalid values."""
        config_content = """
[test]
bad_int = not_a_number
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        result = config.get_int('test', 'bad_int', 99)
        assert result == 99
    
    def test_get_float(self, tmp_path):
        """Test get_float() returns float values."""
        config_content = """
[test]
float_value = 3.14159
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        result = config.get_float('test', 'float_value')
        assert abs(result - 3.14159) < 0.0001
        assert isinstance(result, float)
    
    def test_get_bool_true_values(self, tmp_path):
        """Test get_bool() recognizes true values."""
        config_content = """
[test]
bool_true = true
bool_yes = yes
bool_1 = 1
bool_on = on
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.get_bool('test', 'bool_true') is True
        assert config.get_bool('test', 'bool_yes') is True
        assert config.get_bool('test', 'bool_1') is True
        assert config.get_bool('test', 'bool_on') is True
    
    def test_get_bool_false_values(self, tmp_path):
        """Test get_bool() recognizes false values."""
        config_content = """
[test]
bool_false = false
bool_no = no
bool_0 = 0
bool_off = off
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.get_bool('test', 'bool_false') is False
        assert config.get_bool('test', 'bool_no') is False
        assert config.get_bool('test', 'bool_0') is False
        assert config.get_bool('test', 'bool_off') is False
    
    # ========================================================================
    # DEFAULT VALUE FALLBACKS
    # ========================================================================
    
    def test_missing_section_returns_default(self, tmp_path):
        """Test missing section returns default value."""
        config_content = "[existing_section]\nkey = value"
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.get('missing_section', 'key', 'default') == 'default'
        assert config.get_int('missing_section', 'key', 42) == 42
        assert config.get_float('missing_section', 'key', 1.5) == 1.5
        assert config.get_bool('missing_section', 'key', True) is True
    
    def test_missing_key_returns_default(self, tmp_path):
        """Test missing key returns default value."""
        config_content = "[section]\nexisting_key = value"
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.get('section', 'missing_key', 'default') == 'default'
    
    # ========================================================================
    # ENVIRONMENT VARIABLE OVERRIDES
    # ========================================================================
    
    def test_get_embedding_model_from_env(self, tmp_path):
        """Test get_embedding_model() reads from environment."""
        config_file = tmp_path / "system.ini"
        config_file.write_text("[rag]\n", encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        with patch.dict(os.environ, {'OPENAI_MODEL_EMBEDDING': 'test-embedding-model'}):
            result = config.get_embedding_model()
            assert result == 'test-embedding-model'
    
    def test_get_embedding_model_default(self, tmp_path):
        """Test get_embedding_model() uses default when env not set."""
        config_file = tmp_path / "system.ini"
        config_file.write_text("[rag]\n", encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        # Clear env var if set
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key entirely for this test
            os.environ.pop('OPENAI_MODEL_EMBEDDING', None)
            result = config.get_embedding_model()
            assert result == 'text-embedding-3-large'  # Default value
    
    def test_get_heavy_model_requires_env(self, tmp_path):
        """Test get_heavy_model() raises if env not set."""
        config_file = tmp_path / "system.ini"
        config_file.write_text("[llm]\n", encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('OPENAI_MODEL_HEAVY', None)
            
            with pytest.raises(ValueError, match="OPENAI_MODEL_HEAVY must be set"):
                config.get_heavy_model()
    
    # ========================================================================
    # SPECIFIC CONFIG GETTERS
    # ========================================================================
    
    def test_rag_config_getters(self, tmp_path):
        """Test RAG-specific config getters."""
        config_content = """
[rag]
CHUNK_SIZE_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 75
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_BATCH_SIZE = 50
TOP_K_DOCUMENTS = 10
MIN_SCORE_THRESHOLD = 0.8
QDRANT_SEARCH_LIMIT = 20
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.get_chunk_size_tokens() == 600
        assert config.get_chunk_overlap_tokens() == 75
        assert config.get_embedding_dimensions() == 1536
        assert config.get_embedding_batch_size() == 50
        assert config.get_top_k_documents() == 10
        assert config.get_min_score_threshold() == 0.8
        assert config.get_qdrant_search_limit() == 20
    
    def test_dev_mode_getter(self, tmp_path):
        """Test is_dev_mode() getter."""
        config_content = """
[development]
DEV_MODE = true
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        assert config.is_dev_mode() is True
    
    def test_system_prompt_getter(self, tmp_path):
        """Test get_system_prompt() getter."""
        config_content = """
[application]
system_prompt = You are a helpful assistant.
"""
        config_file = tmp_path / "system.ini"
        config_file.write_text(config_content, encoding='utf-8')
        
        config = ConfigService(config_path=str(config_file))
        
        result = config.get_system_prompt()
        assert result == "You are a helpful assistant."
