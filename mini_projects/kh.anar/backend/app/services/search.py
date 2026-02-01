from typing import List

# A httpx a Google Custom Search hívásokhoz kell. Ha nincs telepítve a futtatási
# környezetben (pl. lokális fejlesztésnél a függőségek nélkül), akkor ezt
# kezeljük, és egyértelmű üzenetet adunk, ha a Google kerül kiválasztásra.
try:
    import httpx
    _HTTPX_AVAILABLE = True
except Exception:
    httpx = None
    _HTTPX_AVAILABLE = False

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from ..core.config import settings


class WebSearchService:
    """Eltávolított webkeresési szolgáltatás.

    A projekt már nem támogatja a webes keresést. Ez a csonk a kompatibilitás
    miatt maradt, de mindig azt jelzi, hogy a keresés nem érhető el.
    """

    def __init__(self) -> None:
        self.google_enabled = False
        self.openai_enabled = False

    @property
    def enabled(self) -> bool:
        return False

    def search(self, query: str):
        return ["Web search has been removed from this project."]
