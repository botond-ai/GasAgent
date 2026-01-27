from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Route = Literal["rag_only", "api_only", "mixed"]
Domain = Literal["it", "legal", "hr", "general"]


@dataclass
class TriageDecision:
    domain: Domain
    route: Route
    city: Optional[str] = None  # for weather tool


def heuristic_domain(query: str) -> Domain:
    q = query.lower()
    if any(k in q for k in ["vpn", "install", "telep", "access", "hiba", "nem működik", "nem mukodik"]):
        return "it"
    if any(k in q for k in ["jogi", "nda", "dpa", "compliance", "levelezőlista", "levelezolista", "jogosultság", "jogosultsag"]):
        return "legal"
    if any(k in q for k in ["onboarding", "offboarding", "szabadság", "szabadsag", "belép", "belep", "kilép", "kilep"]):
        return "hr"
    return "general"


def heuristic_route(query: str) -> tuple[Route, Optional[str]]:
    q = query.lower()
    wants_weather = any(k in q for k in ["időjár", "idojar", "weather", "hőmérséklet", "homerseklet"])
    mentions_docs = any(k in q for k in ["dokument", "policy", "szabály", "szabaly", "docs", "szerint"])

    # naive city extract (minimal): Budapest/City after "itt:" etc
    city = None
    for c in ["budapest", "debrecen", "szeged", "pecs", "pécs", "gyor", "győr"]:
        if c in q:
            city = c.capitalize() if c != "pecs" else "Pécs"
            break

    if wants_weather and mentions_docs:
        return "mixed", city
    if wants_weather:
        return "api_only", city
    return "rag_only", None


def triage_decide(query: str) -> TriageDecision:
    domain = heuristic_domain(query)
    route, city = heuristic_route(query)
    return TriageDecision(domain=domain, route=route, city=city)
