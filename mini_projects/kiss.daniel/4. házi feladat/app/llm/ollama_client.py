"""
Ollama LLM client with model routing, fallback, and JSON enforcement.
Handles HTTP communication with Ollama API.
"""

import json
import logging
import random
import time
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaError(Exception):
    """Base exception for Ollama client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class OllamaClient:
    """
    Thin HTTP client for Ollama API.
    Supports model routing, JSON enforcement, and fallback strategies.
    """
    
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.timeout = self.settings.ollama_timeout_s
        self.temperature = self.settings.ollama_temperature
        self._available_models: Optional[list[str]] = None
        self._client = httpx.Client(timeout=self.timeout)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._client.close()
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def get_available_models(self) -> list[str]:
        """
        Query Ollama for available models.
        Caches result for the lifetime of the client.
        """
        if self._available_models is not None:
            return self._available_models
        
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            self._available_models = [m["name"] for m in data.get("models", [])]
            logger.info(f"Available Ollama models: {self._available_models}")
            return self._available_models
        except httpx.HTTPError as e:
            logger.error(f"Failed to get available models: {e}")
            raise OllamaError(f"Failed to connect to Ollama: {e}", retryable=True)
    
    def validate_model(self, model: str) -> tuple[bool, Optional[str]]:
        """
        Validate that a model is available.
        Returns (is_valid, suggested_fallback).
        """
        available = self.get_available_models()
        
        if model in available:
            return True, None
        
        # Try to find a fallback
        for fallback in self.settings.fallback_models:
            if fallback in available:
                logger.warning(f"Model '{model}' not available, suggesting fallback: {fallback}")
                return False, fallback
        
        return False, None
    
    def validate_configured_models(self) -> dict[str, Any]:
        """
        Validate all configured models at startup.
        Returns validation report with suggestions.
        """
        available = self.get_available_models()
        report = {
            "available_models": available,
            "configured": {},
            "valid": True,
            "errors": [],
            "warnings": [],
        }
        
        tasks = ["planner", "extractor", "summarizer", "final"]
        for task in tasks:
            model = self.settings.get_model_for_task(task)
            is_valid, fallback = self.validate_model(model)
            report["configured"][task] = {
                "model": model,
                "valid": is_valid,
                "fallback": fallback,
            }
            if not is_valid:
                if fallback:
                    report["warnings"].append(
                        f"Model '{model}' for {task} not available. Will use fallback: {fallback}"
                    )
                else:
                    report["errors"].append(
                        f"Model '{model}' for {task} not available and no fallback found."
                    )
                    report["valid"] = False
        
        return report
    
    def _make_request(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        format_json: bool = False,
    ) -> str:
        """
        Make a generate request to Ollama.
        
        Args:
            model: Model name to use
            prompt: User prompt
            system: Optional system prompt
            temperature: Override temperature
            format_json: If True, request JSON format
            
        Returns:
            Response text
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
            },
        }
        
        if system:
            payload["system"] = system
        
        if format_json:
            payload["format"] = "json"
        
        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            
            if response.status_code in self.RETRYABLE_STATUS_CODES:
                raise OllamaError(
                    f"Ollama returned {response.status_code}",
                    status_code=response.status_code,
                    retryable=True,
                )
            
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
            
        except httpx.TimeoutException as e:
            raise OllamaError(f"Ollama timeout: {e}", retryable=True)
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama HTTP error: {e}", retryable=False)
    
    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate text completion.
        
        Args:
            model: Model name
            prompt: User prompt
            system: Optional system prompt
            temperature: Override temperature
            
        Returns:
            Generated text
        """
        return self._make_request(model, prompt, system, temperature, format_json=False)
    
    def generate_json(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """
        Generate JSON response.
        
        Args:
            model: Model name
            prompt: User prompt (should ask for JSON)
            system: Optional system prompt
            temperature: Override temperature
            
        Returns:
            Parsed JSON dict
        """
        response_text = self._make_request(model, prompt, system, temperature, format_json=True)
        
        # Try to parse JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_str = self._extract_json(response_text)
            if json_str:
                return json.loads(json_str)
            raise OllamaError(f"Failed to parse JSON response: {response_text[:200]}")
    
    def generate_structured(
        self,
        model: str,
        prompt: str,
        response_model: Type[T],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 2,
    ) -> T:
        """
        Generate response and validate against Pydantic model.
        Implements fallback to stronger model if validation fails.
        
        Args:
            model: Model name
            prompt: User prompt
            response_model: Pydantic model class for response
            system: Optional system prompt
            temperature: Override temperature
            max_retries: Max retries with fallback models
            
        Returns:
            Validated Pydantic model instance
        """
        # Add JSON schema hint to prompt
        schema_hint = f"\n\nRespond with valid JSON matching this schema:\n{response_model.model_json_schema()}"
        full_prompt = prompt + schema_hint
        
        models_to_try = [model] + self.settings.fallback_models[:max_retries]
        last_error = None
        
        for attempt, try_model in enumerate(models_to_try):
            # Skip if model not available
            is_valid, _ = self.validate_model(try_model)
            if not is_valid:
                continue
            
            try:
                json_data = self.generate_json(try_model, full_prompt, system, temperature)
                return response_model.model_validate(json_data)
            except (OllamaError, ValidationError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"Model {try_model} failed (attempt {attempt + 1}): {e}")
                continue
        
        raise OllamaError(f"All models failed to generate valid response: {last_error}")
    
    def generate_with_retry(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        format_json: bool = False,
        max_retries: Optional[int] = None,
    ) -> str:
        """
        Generate with exponential backoff retry for transient errors.
        
        Args:
            model: Model name
            prompt: User prompt
            system: Optional system prompt
            temperature: Override temperature
            format_json: Request JSON format
            max_retries: Override max retries
            
        Returns:
            Generated text
        """
        retries = max_retries or self.settings.max_retries
        base_delay = self.settings.retry_base_delay
        
        last_error = None
        for attempt in range(retries + 1):
            try:
                return self._make_request(model, prompt, system, temperature, format_json)
            except OllamaError as e:
                last_error = e
                if not e.retryable or attempt == retries:
                    raise
                
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Retry {attempt + 1}/{retries} after {delay:.2f}s: {e}")
                time.sleep(delay)
        
        raise last_error or OllamaError("Unexpected retry failure")
    
    def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """
        Generate embeddings for text.
        
        Args:
            text: Text to embed
            model: Embedding model (default from settings)
            
        Returns:
            Embedding vector
        """
        embed_model = model or self.settings.ollama_embed_model
        
        try:
            response = self._client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": embed_model, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except httpx.HTTPError as e:
            logger.error(f"Embedding failed: {e}")
            raise OllamaError(f"Embedding failed: {e}")
    
    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """Try to extract JSON from text that may have extra content."""
        # Find JSON-like content
        import re
        
        # Try to find object
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                json.loads(match.group())
                return match.group()
            except json.JSONDecodeError:
                pass
        
        # Try to find array
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                json.loads(match.group())
                return match.group()
            except json.JSONDecodeError:
                pass
        
        return None


def get_model_for_task(task: str) -> str:
    """Convenience function to get model for a task."""
    settings = get_settings()
    return settings.get_model_for_task(task)
