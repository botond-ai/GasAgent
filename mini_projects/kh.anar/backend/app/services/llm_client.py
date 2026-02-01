from typing import Any, List, Dict, Optional
import asyncio
import json

from langchain_core.messages import BaseMessage
from openai import OpenAI

from ..core.config import settings


class LLMClient:
    """Burkoló az OpenAI API-k köré, amely visszalép, ha a responses API nem érhető el."""

    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=settings.openai_api_key)

    async def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        history: List[BaseMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> Dict[str, Any]:
        messages = []
        messages.append({"role": "system", "content": system_prompt})
        messages.extend(self._to_openai_messages(history))
        messages.append({"role": "user", "content": user_prompt})

        # Use chat completions with function calling support
        kwargs = {
            "model": settings.model_name,
            "messages": messages,
        }
        
        # Add tools if provided
        if tools:
            kwargs["tools"] = [{"type": "function", "function": tool} for tool in tools]
            kwargs["tool_choice"] = tool_choice
        
        completion = await asyncio.to_thread(
            self.client.chat.completions.create,
            **kwargs
        )
        
        message = completion.choices[0].message
        
        # Check if the model wants to call a tool
        if message.tool_calls:
            return {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments)
                    }
                    for tc in message.tool_calls
                ],
                "content": message.content
            }
        
        # Regular text response
        return {
            "type": "text",
            "content": message.content or ""
        }

    def _to_openai_messages(self, history: List[BaseMessage]) -> List[dict[str, Any]]:
        converted: List[dict[str, Any]] = []
        for msg in history:
            role = "user"
            if getattr(msg, "type", "") == "ai":
                role = "assistant"
            converted.append({"role": role, "content": msg.content})
        return converted
