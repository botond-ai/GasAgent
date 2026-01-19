import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Útvonalak beállítása
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.document_store import VectorStore
from src.weather_tool import WeatherClient  # <--- ÚJ IMPORT

load_dotenv()

def router_logic(query: str) -> str:
    """
    Eldönti a felhasználó szándékát (Intent Detection).
    """
    query_lower = query.lower()
    # Egyszerű kulcsszó alapú routing (később lehet LLM alapú)
    if any(word in query_lower for word in ['idő', 'időjárás', 'fok', 'eső', 'napsütés', 'weather']):
        return "weather"
    else:
        return "rag"

def generate_rag_answer(query: str, context_docs: list) -> str:
    """RAG válasz generálása (ez maradt a régi)."""
    if not context_docs:
        return "Sajnos nem találtam releváns információt a belső tudásbázisban."
    
    context_text = "\n\n".join([f"Forrás ({d.category}): {d.content}" for d in context_docs])
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    system_prompt = "Vállalati asszisztens vagy. Csak a megadott kontextus alapján válaszolj."
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Kontextus:\n{context_text}\n\nKérdés: {query}")
    ])
    return response.content

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'data', 'knowledge_base.json')
    
    # Eszközök inicializálása
    vs = VectorStore(json_path)
    weather_tool = WeatherClient() # <--- ÚJ TOOL

    print("\n🤖 --- Knowledge Router + Weather Agent ---")
    print("Tudok válaszolni céges kérdésekre (pl. 'VPN hiba') és időjárásra is (pl. 'időjárás Budapest').")

    while True:
        user_input = input("\nKérdés: ").strip()
        if user_input.lower() in ['exit', 'kilepes']:
            break
        if not user_input:
            continue

        # 1. Lépés: Döntés (Routing)
        intent = router_logic(user_input)

        if intent == "weather":
            print("🌤️  Időjárás szándék érzékelve. Külső API hívása...")
            
            # Egyszerű város kinyerés (split) - élesben ezt is LLM csinálná
            # Ha a user beírja: "időjárás Budapest", mi kivesszük a 2. szót.
            words = user_input.split()
            city = "Budapest" # Default
            for word in words:
                if word.lower() not in ['mi', 'a', 'az', 'időjárás', 'idő', 'most', 'milyen']:
                    city = word.strip("?,.!")
            
            # API hívás
            weather_data = weather_tool.get_weather(city)
            
            if weather_data['success']:
                print(f"✅ Külső adat sikeresen lekérve: {weather_data}")
                print(f"🌡️  {weather_data['city']}: {weather_data['temp_C']}°C, {weather_data['desc']}")
            else:
                print(f"❌ Hiba az API híváskor: {weather_data.get('error')}")

        else: # intent == "rag"
            print("📂 Belső dokumentum keresés (RAG)...")
            docs = vs.similarity_search(user_input)
            answer = generate_rag_answer(user_input, docs)
            print(f"🤖 {answer}")

if __name__ == "__main__":
    main()