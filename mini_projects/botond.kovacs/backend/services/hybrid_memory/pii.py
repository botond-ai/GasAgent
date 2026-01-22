"""
PII filtering utilities for hybrid memory layers.
Supports placeholder and pseudonymize modes.
"""
import re
import hashlib
from typing import Any, Dict, List

PII_PATTERNS = {
    'EMAIL': r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    'PHONE': r'\+?\d[\d\s\-()]{7,}\d',
}

PLACEHOLDER_MAP = {
    'EMAIL': '[EMAIL]',
    'PHONE': '[PHONE]',
}

def hash_pseudonym(value: str) -> str:
    return '[ID_' + hashlib.sha256(value.encode()).hexdigest()[:8] + ']'

def filter_pii(text: str, mode: str = 'placeholder') -> str:
    for key, pattern in PII_PATTERNS.items():
        if mode == 'placeholder':
            text = re.sub(pattern, PLACEHOLDER_MAP[key], text)
        elif mode == 'pseudonymize':
            text = re.sub(pattern, lambda m: hash_pseudonym(m.group(0)), text)
    return text

def filter_pii_in_layer(layer: Any, mode: str = 'placeholder') -> Any:
    if isinstance(layer, str):
        return filter_pii(layer, mode)
    elif isinstance(layer, list):
        return [filter_pii_in_layer(item, mode) for item in layer]
    elif isinstance(layer, dict):
        return {k: filter_pii_in_layer(v, mode) for k, v in layer.items()}
    return layer
