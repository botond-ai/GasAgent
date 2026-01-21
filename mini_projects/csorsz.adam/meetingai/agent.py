import os
import json
import asyncio
import numpy as np
import requests  
from typing import Any, Dict, List
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# --- RAG INFRASTRUKTÚRA ---
import faiss
from sentence_transformers import SentenceTransformer

class SimpleRAG:
    """Valódi RAG implementáció Vector Database-szel."""
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.chunks = []

    def add_documents(self, text: str):
        self.chunks = [c.strip() for c in text.split('\n') if len(c.strip()) > 15]
        if not self.chunks:
            return
        embeddings = self.model.encode(self.chunks)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))

    def search(self, query: str, top_k: int = 2):
        if self.index is None or not self.chunks:
            return ""
        query_embedding = self.model.encode([query]).astype('float32')
        distances, indices = self.index.search(query_embedding, top_k)
        results = [self.chunks[i] for i in indices[0] if i != -1]
        return "\n".join(results)

# --- KÖRNYEZETI VÁLTOZÓK ---
current_dir = Path(__file__).parent.parent 
env_path = current_dir / 'apikulcs.env'
load_dotenv(dotenv_path=env_path)

_openai_client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"), 
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=300.0
)

try:
    from .sentiment_client import AsyncSentimentClient
except ImportError:
    from sentiment_client import AsyncSentimentClient

class MeetingAgent:
    """Összetett Multi-Tool ágens (8. óra HW - Plan-and-Execute)."""

    def __init__(self, openai_key: str | None = None):
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.weather_api_key = os.getenv("OPENWEATHER_API_KEY")
        self.sentiment_client = AsyncSentimentClient()
        self.rag = SimpleRAG()

    def _get_weather_external(self, city: str) -> Dict[str, Any]:
        if not self.weather_api_key:
            return {"error": "Hiányzó OpenWeather API kulcs!"}
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.weather_api_key}&units=metric&lang=hu"
        try:
            response = requests.get(url, timeout=10)
            data = response.json() 
            if response.status_code != 200:
                return {"error": data.get("message", "Ismeretlen hiba")}
            return {
                "source": "OpenWeatherMap API",
                "city": data.get("name"),
                "temp": data.get("main", {}).get("temp"),
                "description": data.get("weather", [{}])[0].get("description")
            }
        except Exception as e:
            return {"error": str(e)}

    async def _call_planner(self, context: str) -> Dict[str, Any]:
        """❌ 8. ÓRA ÚJDONSÁG: Multi-tool tervezés. Az LLM egy listát ad vissza a teendőkről."""
        system = (
            "You are a strategic meeting planner. Analyze the context and decide which tools to use. "
            "You can choose MULTIPLE tools if necessary. Reply ONLY with a JSON object."
        )
        prompt = (
            "Available tools:\n"
            "1. 'get_weather': Use if location or outdoor plans are mentioned.\n"
            "2. 'analyze_sentiment': Use if mood, tension, or satisfaction is mentioned.\n\n"
            "Context:\n" + context + "\n\n"
            "Respond in this format: {\"tools\": [\"tool1\", \"tool2\"], \"city\": \"city_name\", \"reason\": \"...\"}"
        )

        try:
            resp = _openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "local-model"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.0,
            )
            text_out = resp.choices[0].message.content
            start = text_out.find('{')
            end = text_out.rfind('}') + 1
            return json.loads(text_out[start:end])
        except:
            return {"tools": [], "reason": "Hiba a tervezés során."}

    async def run(self, notes: str) -> Dict[str, Any]:
        """Multi-tool munkafolyamat futtatása."""
        # 1. RAG Indexelés
        self.rag.add_documents(notes)
        
        # 2. Retrieval - mindkét témára keresünk
        relevant_context = self.rag.search("weather, city, location, mood, feelings, satisfaction")
        
        # 3. Planning - az ágens eldönti az eszköztárat
        plan = await self._call_planner(relevant_context)
        tools_to_run = plan.get("tools", [])
        
        result: Dict[str, Any] = {
            "agent_plan": plan,
            "tool_outputs": {}
        }

        for tool in tools_to_run:
            if tool == "get_weather":
                city = plan.get("city", "Budapest")
                result["tool_outputs"]["weather"] = self._get_weather_external(city)

            if tool == "analyze_sentiment":
                sent = await self.sentiment_client.analyze(relevant_context)
                result["tool_outputs"]["sentiment"] = sent

        return result