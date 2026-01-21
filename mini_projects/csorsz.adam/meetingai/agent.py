import os
import json
import asyncio
import numpy as np
import requests  
from typing import Any, Dict
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
        """Dokumentum feldarabolása és indexelése."""
        self.chunks = [c.strip() for c in text.split('\n') if len(c.strip()) > 15]
        if not self.chunks:
            return
        embeddings = self.model.encode(self.chunks)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))

    def search(self, query: str, top_k: int = 2):
        """Releváns információ kikeresése."""
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
    """RAG-alapú MeetingAI ügynök, kiegészítve Külső Időjárás API-val (7. óra HW)."""

    def __init__(self, openai_key: str | None = None):
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.weather_api_key = os.getenv("OPENWEATHER_API_KEY") # ❌ HW: API kulcs betöltése
        self.sentiment_client = AsyncSentimentClient()
        self.rag = SimpleRAG()

    def _get_weather_external(self, city: str) -> Dict[str, Any]:
        """❌ 7. ÓRA HÁZI: Külső API integráció és JSON válasz lekérése."""
        if not self.weather_api_key:
            return {"error": "Hiányzó OpenWeather API kulcs az apikulcs.env fájlból!"}
        
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.weather_api_key}&units=metric&lang=hu"
        
        try:
            response = requests.get(url, timeout=10)
            # A feladat lényege: JSON válasz lekérése és feldolgozása
            data = response.json() 
            
            if response.status_code != 200:
                return {"error": data.get("message", "Ismeretlen hiba")}
            
            return {
                "source": "OpenWeatherMap API",
                "city": data.get("name"),
                "temp": data.get("main", {}).get("temp"),
                "description": data.get("weather", [{}])[0].get("description"),
                "full_json_response": data
            }
        except Exception as e:
            return {"error": f"API hívási hiba: {str(e)}"}

    async def _call_planner(self, context: str) -> Dict[str, Any]:
        """LLM döntéshozatal: kell-e külső eszköz (Sentiment vagy Időjárás)."""
        system = "You are a meeting analyst. Reply in JSON."
        prompt = (
            "Based on the context, decide if we need a tool. \n"
            "If the user asks about weather, tool: 'get_weather'.\n"
            "If there is tension, tool: 'analyze_sentiment'.\n"
            "Context:\n" + context
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
            return {"call_tool": False}

    async def run(self, notes: str) -> Dict[str, Any]:
        """A teljes munkafolyamat futtatása."""
        # 1. RAG Indexelés
        self.rag.add_documents(notes)
        
        # 2. Retrieval (keresünk időjárásra is utaló nyomokat a jegyzetben)
        relevant_context = self.rag.search("weather, location, mood and decisions")
        
        # 3. Planning
        plan = await self._call_planner(relevant_context)
        
        result: Dict[str, Any] = {
            "plan": plan,
            "retrieved_context": relevant_context
        }

        
        if plan.get("tool") == "get_weather":
            city = plan.get("city", "Budapest")
            result["weather_output"] = self._get_weather_external(city)

        elif plan.get("tool") == "analyze_sentiment":
            sent = await self.sentiment_client.analyze(relevant_context)
            result["tool_output"] = sent

        return result