"""Groq LLM client wrapper."""
import json
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


class GroqClient:
    """Wrapper for Groq LLM interactions."""
    
    def __init__(self, model: str = "llama-3.3-70b-versatile", temperature: float = 0.1):
        """Initialize Groq client.
        
        Args:
            model: Model name to use (Groq models - suitable for tool-using agents)
            temperature: Sampling temperature (lower = more deterministic)
        """
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        self.llm = ChatGroq(
            model=model,
            temperature=temperature,
            max_tokens=500,  # Enough for JSON responses
            groq_api_key=api_key
        )
    
    def invoke(self, system_prompt: str, user_message: str) -> str:
        """Invoke the LLM with a system prompt and user message.
        
        Args:
            system_prompt: System-level instructions
            user_message: User input or formatted prompt
            
        Returns:
            LLM response as string
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def invoke_json(self, system_prompt: str, user_message: str) -> dict:
        """Invoke the LLM expecting a JSON response.
        
        Args:
            system_prompt: System-level instructions
            user_message: User input or formatted prompt
            
        Returns:
            Parsed JSON response as dict
            
        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        response = self.invoke(system_prompt, user_message)
        
        # Try to extract JSON from response (LLM might wrap it in markdown)
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        return json.loads(response)
