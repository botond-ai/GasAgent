"""
OpenAI LLM client implementation for RAG.

Purpose:
- Generate natural language responses using retrieved context
- Communicate with OpenAI's Chat Completions API
- Implement the LLM interface for text generation

Design notes:
- Implements the LLM interface
- Uses requests library for HTTP communication
- Formats retrieved documents as context for the LLM
"""

from typing import List, Optional, Dict
import requests
import json

from scripts.interfaces import LLM


class OpenAILLMClient(LLM):
    """
    Concrete LLM implementation using OpenAI's Chat Completions API.
    """

    # Default OpenAI chat completions endpoint
    DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        token: str,
        model_name: str = "gpt-4o-mini",
        endpoint: str | None = None,
    ) -> None:
        """
        Create a new LLM client.

        Args:
            token: OpenAI API key used for authentication.
            model_name: Name of the chat model (e.g., gpt-4o-mini, gpt-3.5-turbo).
            endpoint: Optional override for the API endpoint.
        """
        self._token = token
        self._model = model_name
        self._endpoint = endpoint or self.DEFAULT_ENDPOINT

    def generate(
        self,
        prompt: str,
        context: List[str],
        max_tokens: int = 500,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate a response based on the prompt and retrieved context.

        Args:
            prompt: The user's question or query.
            context: List of relevant document chunks retrieved from vector search.
            max_tokens: Maximum number of tokens to generate.
            conversation_history: Optional list of previous messages [{"role": "user/assistant", "content": "..."}].

        Returns:
            Generated response text from the LLM.
        """
        try:
            # Format context documents into a single string
            context_text = self._format_context(context)

            # Build the system message with instructions
            system_message = (
                "You are a helpful assistant that answers questions based on the provided context. "
                "Use the context below to answer the user's question. "
                "If the answer cannot be found in the context, say so clearly."
            )

            # Build messages for the chat API
            messages = [
                {"role": "system", "content": system_message}
            ]

            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)

            # Add current context and query
            messages.append({
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {prompt}"
            })

            # Prepare request headers and payload
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            }

            payload = {
                "model": self._model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }

            # Make the API request
            response = requests.post(
                self._endpoint,
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            # Parse and return the response
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"Error generating LLM response (HTTP request failed): {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            raise
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"Error parsing API response: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error generating LLM response: {e}")
            raise

    def _format_context(self, context: List[str]) -> str:
        """
        Format retrieved document chunks into a readable context string.

        Args:
            context: List of document chunk texts.

        Returns:
            Formatted context string with numbered chunks.
        """
        if not context:
            return "No relevant context found."

        formatted_chunks = []
        for i, chunk in enumerate(context, 1):
            formatted_chunks.append(f"[{i}] {chunk}")

        return "\n\n".join(formatted_chunks)
