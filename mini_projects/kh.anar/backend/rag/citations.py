"""Hivatkozás-leképező

A visszakeresett találatok és a végső válasz alapján megmondja, mely darabok
szerepeltek hivatkozásként. A tesztelhetőség kedvéért külön modulban marad.
"""
from typing import List, Dict


def map_citations(answer_text: str, hits: List[Dict]):
    # naiv megvalósítás: bármely találatot megjelölünk, ha a darab szövege vagy a dokumentum címe
    # szerepel az answer_text-ben. Összetettebb megoldás lehetne n-gram átfedés vagy
    # modellalapú hozzárendelés; itt egyszerűen és determinisztikusan tartjuk a tesztekhez.
    cited = []
    for h in hits:
        if h.get("document") and (h["document"][:100] in answer_text or (h.get("metadata", {}).get("title") or "") in answer_text):
            cited.append({"id": h["id"], "doc_id": h.get("metadata", {}).get("doc_id"), "title": h.get("metadata", {}).get("title")})
    return cited
