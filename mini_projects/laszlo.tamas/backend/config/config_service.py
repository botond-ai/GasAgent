"""
Configuration Service - system.ini Reader

Provides centralized access to system.ini configuration values.
"""

import configparser
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Singleton pattern for config parser
_config: Optional[configparser.ConfigParser] = None
_config_path = Path(__file__).parent / "system.ini"


def _load_config() -> configparser.ConfigParser:
    """Load system.ini configuration file (singleton)."""
    global _config
    
    if _config is None:
        _config = configparser.ConfigParser()
        if _config_path.exists():
            _config.read(_config_path, encoding='utf-8')
            logger.info(f"Loaded configuration from {_config_path}")
        else:
            logger.warning(f"Configuration file not found: {_config_path}")
    
    return _config


def get_config_value(section: str, key: str, fallback: Any = None) -> Any:
    """
    Get configuration value from system.ini.
    
    Args:
        section: Configuration section (e.g., 'application', 'rag')
        key: Configuration key (e.g., 'APP_VERSION', 'TOP_K_DOCUMENTS')
        fallback: Default value if key not found
    
    Returns:
        Configuration value or fallback
    
    Example:
        >>> get_config_value('application', 'APP_VERSION', '0.0.0')
        '0.2.0'
    """
    config = _load_config()
    
    try:
        if section in config and key in config[section]:
            value = config[section][key]
            
            # Type conversion based on value
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'
            
            try:
                # Try integer
                return int(value)
            except ValueError:
                try:
                    # Try float
                    return float(value)
                except ValueError:
                    # Return as string
                    return value
        else:
            logger.debug(f"Config key [{section}].{key} not found, using fallback: {fallback}")
            return fallback
    
    except Exception as e:
        logger.error(f"Error reading config [{section}].{key}: {e}")
        return fallback


def reload_config() -> None:
    """Force reload of configuration from system.ini."""
    global _config
    _config = None
    logger.info("Configuration reloaded")


def get_rag_guidelines(language: str) -> Optional[str]:
    """
    Load RAG answer guidelines from external text file.
    
    Args:
        language: Language code (e.g., 'hu', 'en')
    
    Returns:
        RAG guidelines text or None if file not found
    
    Example:
        >>> get_rag_guidelines('hu')
        'FONTOS VÁLASZADÁSI SZABÁLYOK a dokumentumok alapján:...'
    """
    guidelines_file = Path(__file__).parent / f"rag_guidelines_{language.lower()}.txt"
    
    try:
        if guidelines_file.exists():
            content = guidelines_file.read_text(encoding='utf-8').strip()
            logger.debug(f"Loaded RAG guidelines from {guidelines_file}")
            return content
        else:
            logger.warning(f"RAG guidelines file not found: {guidelines_file}")
            return None
    except Exception as e:
        logger.error(f"Error reading RAG guidelines file {guidelines_file}: {e}")
        return None


def get_tool_routing_instructions() -> Optional[str]:
    """
    Load tool routing instructions (AVAILABLE TOOLS + DECISION LOGIC) from external text file.
    
    This file contains 601 tokens of static content to ensure OpenAI Prompt Cache
    reaches the 1024-token minimum for cache activation.
    
    Returns:
        Tool routing instructions text or None if file not found
    
    Example:
        >>> get_tool_routing_instructions()
        'AVAILABLE TOOLS:\\n- store_memory: Store important facts...'
    """
    instructions_file = Path(__file__).parent / "tool_routing_instructions.txt"
    
    try:
        if instructions_file.exists():
            content = instructions_file.read_text(encoding='utf-8').strip()
            logger.debug(f"Loaded tool routing instructions from {instructions_file}")
            return content
        else:
            logger.warning(f"Tool routing instructions file not found: {instructions_file}")
            return None
    except Exception as e:
        logger.error(f"Error reading tool routing instructions file {instructions_file}: {e}")
        return None
