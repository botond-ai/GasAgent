import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any, Dict

# --- KÖRNYEZETI VÁLTOZÓK BETÖLTÉSE ---
# Megkeressük az apikulcs.env fájlt a szülőmappában
current_dir = Path(__file__).parent.parent 
env_path = current_dir / 'apikulcs.env'
load_dotenv(dotenv_path=env_path)

# Globális kliens inicializálása az LM Studio-hoz
_openai_client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"), 
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=300.0  # Legyen elég idő a válaszra
)

class AsyncSentimentClient:
    """Asynchronous sentiment analysis client for LM Studio and HuggingFace."""

    def __init__(self, hf_model: str | None = None):
        self.hf_token = os.environ.get("HUGGINGFACE_API_TOKEN")
        self.hf_model = hf_model or os.environ.get("HUGGINGFACE_MODEL") or "distilbert-base-uncased-finetuned-sst-2-english"
        self.openai_key = os.environ.get("OPENAI_API_KEY")

    async def analyze(self, text: str) -> Dict[str, Any]:
        if self.hf_token:
            return await self._analyze_hf(text)
        if self.openai_key:
            return await self._analyze_openai(text)
        raise RuntimeError("No sentiment API token configured (set HUGGINGFACE_API_TOKEN or OPENAI_API_KEY)")

    async def _analyze_hf(self, text: str) -> Dict[str, Any]:
        url = f"https://api-inference.huggingface.co/models/{self.hf_model}"
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json={"inputs": text}, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        sentiment = "neutral"
        try:
            if isinstance(data, list) and data:
                label = data[0].get("label", "").upper()
                if "NEGATIVE" in label:
                    sentiment = "frustrated"
                elif "POSITIVE" in label:
                    sentiment = "satisfied"
        except Exception:
            pass

        return {"sentiment": sentiment, "raw": "HF API response"}

    async def _analyze_openai(self, text: str) -> Dict[str, Any]:
        system = "You are a sentiment classification assistant. Reply ONLY with valid JSON."
        prompt = (
            "Classify the sentiment of the following text and reply ONLY with a JSON object:\n"
            "{\"sentiment\": \"frustrated|neutral|satisfied\", \"explanation\": \"...\"}\n---\n" + text
        )

        try:
            resp = _openai_client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "local-model"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=500, # Megnövelve, hogy a <think> blokk is beleférjen
                temperature=0.0,
            )

            text_out = resp.choices[0].message.content.strip()

            # --- QWEN / REASONING MODEL FIX ---
            # Ha a modell "gondolkodik" (<think>), azt levágjuk a JSON feldolgozás előtt
            if "</think>" in text_out:
                text_out = text_out.split("</think>")[-1].strip()

            # JSON keresése (ha még mindig lenne körötte szöveg)
            start_idx = text_out.find('{')
            end_idx = text_out.rfind('}') + 1
            if start_idx != -1:
                json_str = text_out[start_idx:end_idx]
                parsed = json.loads(json_str)
                return {
                    "sentiment": parsed.get("sentiment", "neutral"),
                    "explanation": parsed.get("explanation", ""),
                    "status": "success"
                }
            
            return {"sentiment": "neutral", "explanation": "Could not parse JSON", "raw_text": text_out}

        except Exception as e:
            return {"sentiment": "neutral", "error": str(e)}