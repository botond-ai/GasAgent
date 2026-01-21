"""
LLM Cost Calculation

Pricing data for OpenAI models used in Knowledge Router.

Pricing source: 
1. system.ini [pricing] section (primary)
2. Hardcoded defaults (fallback if config not available)

Pricing reference: OpenAI Pricing Page (as of 2026-01-17)
https://openai.com/pricing

Usage:
    from observability.cost_tracker import calculate_cost, get_model_pricing
    
    cost = calculate_cost(
        model="gpt-4o",
        prompt_tokens=1234,
        completion_tokens=567
    )
"""

from typing import Dict, Tuple

def _load_pricing_from_config() -> Dict[str, Dict[str, float]]:
    """
    Load pricing from system.ini [pricing] section.
    
    Returns:
        Dict with model pricing data
    """
    try:
        from config.config_service import get_config_value
        
        return {
            # GPT-5 models (2026 pricing)
            "gpt-5-nano": {
                "input": float(get_config_value("pricing", "GPT5_NANO_INPUT_PRICE", "0.05")),
                "output": float(get_config_value("pricing", "GPT5_NANO_OUTPUT_PRICE", "0.40")),
                "cache_discount": float(get_config_value("pricing", "GPT5_NANO_CACHE_DISCOUNT", "0.90")),
            },
            "gpt-5-mini": {
                "input": float(get_config_value("pricing", "GPT5_MINI_INPUT_PRICE", "0.25")),
                "output": float(get_config_value("pricing", "GPT5_MINI_OUTPUT_PRICE", "2.00")),
                "cache_discount": float(get_config_value("pricing", "GPT5_MINI_CACHE_DISCOUNT", "0.90")),
            },
            
            # GPT-4.1 models
            "gpt-4.1": {
                "input": float(get_config_value("pricing", "GPT4_1_INPUT_PRICE", "2.00")),
                "output": float(get_config_value("pricing", "GPT4_1_OUTPUT_PRICE", "8.00")),
                "cache_discount": float(get_config_value("pricing", "GPT4_1_CACHE_DISCOUNT", "0.75")),
            },
            "gpt-4.1-mini": {
                "input": float(get_config_value("pricing", "GPT4_1_MINI_INPUT_PRICE", "0.40")),
                "output": float(get_config_value("pricing", "GPT4_1_MINI_OUTPUT_PRICE", "1.60")),
                "cache_discount": float(get_config_value("pricing", "GPT4_1_MINI_CACHE_DISCOUNT", "0.75")),
            },
            
            # GPT-4o models
            "gpt-4o": {
                "input": float(get_config_value("pricing", "GPT4O_INPUT_PRICE", "2.50")),
                "output": float(get_config_value("pricing", "GPT4O_OUTPUT_PRICE", "10.00")),
                "cache_discount": float(get_config_value("pricing", "GPT4O_CACHE_DISCOUNT", "0.50")),
            },
            "gpt-4o-mini": {
                "input": float(get_config_value("pricing", "GPT4O_MINI_INPUT_PRICE", "0.15")),
                "output": float(get_config_value("pricing", "GPT4O_MINI_OUTPUT_PRICE", "0.60")),
                "cache_discount": float(get_config_value("pricing", "GPT4O_MINI_CACHE_DISCOUNT", "0.50")),
            },
            
            # GPT-3.5 models
            "gpt-3.5-turbo": {
                "input": float(get_config_value("pricing", "GPT35_TURBO_INPUT_PRICE", "0.50")),
                "output": float(get_config_value("pricing", "GPT35_TURBO_OUTPUT_PRICE", "1.50")),
            },
            
            # Embedding models
            "text-embedding-3-large": {
                "input": float(get_config_value("pricing", "EMBEDDING_3_LARGE_INPUT_PRICE", "0.13")),
                "output": 0.0,
            },
            "text-embedding-3-small": {
                "input": float(get_config_value("pricing", "EMBEDDING_3_SMALL_INPUT_PRICE", "0.02")),
                "output": 0.0,
            },
            "text-embedding-ada-002": {
                "input": float(get_config_value("pricing", "EMBEDDING_ADA_002_INPUT_PRICE", "0.10")),
                "output": 0.0,
            },
        }
    except Exception:
        # Fallback to hardcoded pricing if config service fails
        return _get_default_pricing()


def _get_default_pricing() -> Dict[str, Dict[str, float]]:
    """
    Fallback hardcoded pricing (used if system.ini not available).
    
    Returns:
        Dict with default model pricing
    """
    return {
        # GPT-4o models
        "gpt-4o": {
            "input": 2.50,
            "output": 10.00,
        },
        "gpt-4o-mini": {
            "input": 0.15,
            "output": 0.60,
        },
        
        # GPT-3.5 models
        "gpt-3.5-turbo": {
            "input": 0.50,
            "output": 1.50,
        },
        
        # Embedding models
        "text-embedding-3-large": {
            "input": 0.13,
            "output": 0.0,
        },
        "text-embedding-3-small": {
            "input": 0.02,
            "output": 0.0,
        },
        "text-embedding-ada-002": {
            "input": 0.10,
            "output": 0.0,
        },
    }


# ============================================================================
# MODEL PRICING (loaded from system.ini or defaults)
# ============================================================================

MODEL_PRICING = _load_pricing_from_config()

# Fallback pricing for unknown models (conservative estimate)
def _get_default_fallback_pricing() -> Dict[str, float]:
    """Get fallback pricing for unknown models from config or defaults."""
    try:
        from config.config_service import get_config_value
        return {
            "input": float(get_config_value("pricing", "DEFAULT_INPUT_PRICE", "5.00")),
            "output": float(get_config_value("pricing", "DEFAULT_OUTPUT_PRICE", "15.00")),
        }
    except Exception:
        return {"input": 5.00, "output": 15.00}

DEFAULT_PRICING = _get_default_fallback_pricing()


# ============================================================================
# COST CALCULATION
# ============================================================================

def get_model_pricing(model: str) -> Dict[str, float]:
    """
    Get pricing for a model.
    
    Args:
        model: Model name (e.g., "gpt-4o", "gpt-3.5-turbo")
    
    Returns:
        Dict with "input" and "output" prices (USD per 1M tokens)
    """
    # Normalize model name (remove org prefix, version suffixes)
    normalized_model = model.lower().strip()
    
    # Try exact match
    if normalized_model in MODEL_PRICING:
        return MODEL_PRICING[normalized_model]
    
    # Try partial match (e.g., "gpt-4o-2024-05-13" → "gpt-4o")
    for known_model in MODEL_PRICING:
        if normalized_model.startswith(known_model):
            return MODEL_PRICING[known_model]
    
    # Fallback to default pricing
    return DEFAULT_PRICING


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int = 0,
    cached_tokens: int = 0
) -> float:
    """
    Calculate cost in USD for an LLM API call (cache-aware).
    
    Args:
        model: Model name (e.g., "gpt-4.1", "gpt-5-nano")
        prompt_tokens: Total number of input tokens
        completion_tokens: Number of output tokens (0 for embeddings)
        cached_tokens: Number of cached input tokens (discounted)
    
    Returns:
        Cost in USD (float)
    
    Example:
        >>> calculate_cost("gpt-4.1", prompt_tokens=2000, completion_tokens=500, cached_tokens=1500)
        # Breakdown:
        # - Uncached: 500 tokens × $2.00/1M = $0.001000
        # - Cached:  1500 tokens × $0.50/1M = $0.000750  (75% discount)
        # - Output:   500 tokens × $8.00/1M = $0.004000
        # Total:                              $0.005750
    """
    import logging
    logger = logging.getLogger(__name__)
    
    pricing = get_model_pricing(model)
    
    # Separate cached vs uncached prompt tokens
    uncached_prompt_tokens = prompt_tokens - cached_tokens
    
    # Get cache discount rate (default 0 if not specified)
    cache_discount = pricing.get("cache_discount", 0.0)
    cached_input_rate = pricing["input"] * (1 - cache_discount)
    
    # Calculate costs
    uncached_cost = (uncached_prompt_tokens / 1_000_000) * pricing["input"]
    cached_cost = (cached_tokens / 1_000_000) * cached_input_rate
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    
    total_cost = uncached_cost + cached_cost + output_cost
    
    # Log breakdown for cache transparency
    if cached_tokens > 0:
        savings = (cached_tokens / 1_000_000) * pricing["input"] * cache_discount
        logger.debug(
            f"[COST] {model}: uncached=${uncached_cost:.6f} + "
            f"cached=${cached_cost:.6f} (saved ${savings:.6f}) + "
            f"output=${output_cost:.6f} = ${total_cost:.6f}"
        )
    
    return total_cost


def format_cost(cost: float) -> str:
    """
    Format cost as human-readable string.
    
    Args:
        cost: Cost in USD
    
    Returns:
        Formatted string (e.g., "$0.0075", "$1.23")
    """
    if cost < 0.01:
        return f"${cost:.6f}"
    elif cost < 1:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"
