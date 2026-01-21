# 🧠 Knowledge Router & Weather Agent

Ez a projekt egy intelligens ágens prototípusa, amely képes **routing (útválasztó)** logikát alkalmazni a felhasználó szándéka alapján. Két fő modult integrál: egy belső vállalati tudásbázist (RAG alapú kereséssel) és egy külső időjárás-lekérdező eszközt.

## 🚀 Funkciók

1. **Intent Routing:** A rendszer felismeri, hogy a felhasználó belső céges információt keres (pl. "VPN hiba") vagy külső adatot (pl. "időjárás").
2. **RAG (Retrieval-Augmented Generation):**
    * **Vector Store:** ChromaDB használata a dokumentumok tárolására.
    * **Embeddings:** OpenAI `text-embedding-3-small` modell a szemantikus kereséshez.
    * **LLM:** GPT-4o a válaszok generálásához (ha van érvényes API kulcs).
3. **Weather Tool (External API):**
    * Integráció a `wttr.in` REST API-val.
    * **Resiliency:** Beépített hibatűrés és "Demo Mód". Ha az API nem elérhető (timeout) vagy hibás a bemenet, a rendszer nem omlik össze, hanem mock adatot szolgáltat.
4. **Minőségbiztosítás:**
    * Objektum-orientált felépítés (`src/` mappa).
    * Automatizált tesztek (`pytest`).

## 🛠️ Telepítés

A projekt Python 3.10+ környezetet igényel.

1. **Klónozás és belépés:**

    ```bash

   cd knowledge_router
