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


## 8. órai házi feladat: Multi-tool Agent (Plan-and-Execute)

### Implementáció leírása
A rendszert átalakítottam egy összetett ágenssé, amely a 8. órai anyagban bemutatott **Plan-and-Execute** mintát követi:
- **Planner Node**: Az LLM (Llama 3.1) elemzi a jegyzetet, és egy listát (`tools`) állít össze a szükséges teendőkről.
- **Executor Node**: Az ágens végigmegy a listán, és egymás után (vagy párhuzamosan) futtatja a kiválasztott eszközöket.
- **Routing**: A modell döntése alapján az ágens képes dinamikusan választani a `get_weather` és az `analyze_sentiment` toolok között, akár mindkettőt aktiválva.

### Sikeres Multi-tool Teszt kimenet
Az alábbi JSON bizonyítja, hogy az ágens képes egyetlen futás alatt több eszközt is összehangolni:

 python run_agent.py notes.txt
{
  "agent_plan": {
    "tools": [
      "get_weather",
      "analyze_sentiment"
    ],
    "city": "Budapest",
    "reason": "Location (Margit-sziget) and mood/tension mentioned"
  },
  "tool_outputs": {
    "weather": {
      "source": "OpenWeatherMap API",
      "city": "Budapest",
      "temp": -2.19,
      "description": "erős felhőzet"
    },
    "sentiment": {
      "sentiment": "frustrated",
      "explanation": "The text mentions that the team members are 'dühösek' (angry) and there is 'nagyon nagy a feszültség' (very high tension), indicating a negative sentiment.",
      "status": "success"
    }
  }
}