# MeetingAI - RAG & Weather Agent Project

## Implementált funkciók (HW2 & HW7)

### 1. RAG Infrastruktúra (Retrieval-Augmented Generation)
- **Vector Database**: FAISS (Facebook AI Similarity Search) a nagy sebességű kereséshez.
- **Embeddings**: `all-MiniLM-L6-v2` modell a szövegek szemantikai reprezentációjához.
- **Document Retrieval**: Intelligens keresés, amely csak a releváns szövegrészleteket továbbítja az LLM-nek.
- **Workflow**: Chunking -> Embedding -> FAISS Indexing -> Semantic Search.

### 2. Külső API Integráció (7. órai házi feladat)
- **Külső API**: **OpenWeatherMap** integráció az aktuális időjárási adatok lekéréséhez.
- **JSON Feldolgozás**: Az ágens képes a külső REST API-tól kapott nyers JSON válaszokat fogadni, feldolgozni és az állapotában (State) tárolni.
- **Tool-Calling**: Az LLM (Llama 3.1) önállóan dönti el a kontextus alapján, hogy mikor szükséges külső API hívást indítani a belső keresés (RAG) helyett vagy mellett.

### 3. Lokális Modell Támogatás
- Az ágens **LM Studio**-n keresztül futtatott lokális modellekkel (az én esetemben a Meta-Llama-3.1-8B-Instruct) kommunikál OpenAI-kompatibilis API-n keresztül.

## Beállítások

1. Telepítse a szükséges könyvtárakat:
   `pip install faiss-cpu sentence-transformers openai python-dotenv requests`


## Manuális Tesztelési Jegyzet (Minőségbiztosítás)
Mivel az automata unit tesztek még fejlesztés alatt állnak, a rendszert integrációs teszttel ellenőriztem.

**Teszt eset:** Időjárás lekérése meeting jegyzet alapján.
- **Input:** "A következő csapatépítőt Budapesten tartjuk... nézd meg az aktuális időjárást!"
- **Folyamat:** RAG (retrieval) -> LLM Planner (decision) -> Weather API (external tool) -> JSON parsing.
- **Eredmény:** Az ágens sikeresen generált tool-hívást, lekérte a -2.05 fokos adatot és a teljes JSON struktúrát.

## Futtatás
`python run_agent.py notes.txt`
python run_agent.py notes.txt
{
  "plan": {
    "tool": "get_weather",
    "reason": "The user asked about the weather in Budapest to plan for an outdoor event."
  },
  "retrieved_context": "A következő csapatépítőt Budapesten tartjuk a szabadban, a Margit-szigeten.\nKérlek, nézd meg az aktuális időjárást Budapesten, hogy tudjunk tervezni a kerti partival!",
  "weather_output": {
    "source": "OpenWeatherMap API",
    "city": "Budapest",
    "temp": -2.05,
    "description": "erős felhőzet",
    "full_json_response": {
      "coord": {
        "lon": 19.0399,
        "lat": 47.498
      },
      "weather": [
        {
          "id": 803,
          "main": "Clouds",
          "description": "erős felhőzet",
          "icon": "04d"
        }
      ],
      "base": "stations",
      "main": {
        "temp": -2.05,
        "feels_like": -6.05,
        "temp_min": -2.71,
        "temp_max": -0.64,
        "pressure": 1015,
        "humidity": 78,
        "sea_level": 1015,
        "grnd_level": 992
      },
      "visibility": 9000,
      "wind": {
        "speed": 3.09,
        "deg": 110
      },
      "clouds": {
        "all": 79
      },
      "dt": 1769003120,
      "sys": {
        "type": 2,
        "id": 2009313,
        "country": "HU",
        "sunrise": 1768976547,
        "sunset": 1769009240
      },
      "timezone": 3600,
      "id": 3054643,
      "name": "Budapest",
      "cod": 200
    }
  }
}