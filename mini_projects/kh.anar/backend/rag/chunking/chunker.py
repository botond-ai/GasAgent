"""Determinista daraboló

Ez a daraboló determinisztikusan osztja fel a dokumentumot szóközöknél
`chunk_size` hosszú darabokra, ahol az egymást követő darabok között
`chunk_overlap` karakter az átfedés.

Miért így: a karakteralapú darabolás nyelvfüggetlen, egyszerű és
determinisztikus (nincs benne véletlen). Az átfedés segít megőrizni a
kontextust a határszélek mentén; a chunk_size/overlap paraméterezhető, hogy
egyensúlyban legyen a kontextusablak és a RAG visszakeresés.
"""
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict


class DeterministicChunker:
    """Daraboló, amely a szöveget determinisztikusan karakterhossz szerint osztja.

    Nem a legnyelvtudatosabb megközelítés, de determinisztikus és könnyű tesztelni.
    Csereügyletek:
      - Előnyök: determinisztikus, egyszerű, hordozható
      - Hátrányok: mondatok között is vághat, amit a chunk_size és overlap
        hangolásával lehet enyhíteni.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 128):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, doc_id: str, text: str, doc_metadata: Dict = None) -> List[Chunk]:
        """Visszaadja a megadott dokumentum szövegéhez tartozó Chunk objektumok listáját.

        Determinisztikus: ugyanaz a bemenet mindig ugyanazokat az azonosítókat és darabokat adja.
        A chunk azonosítók formátuma: `doc_id:idx`.
        
        Args:
            doc_id: Dokumentumazonosító
            text: A darabolandó szövegtartalom
            doc_metadata: Opcionális metaadatok minden darabhoz (pl. cím, forrás, oldal)
        """
        chunks: List[Chunk] = []
        start = 0
        idx = 0
        length = len(text)
        base_metadata = doc_metadata or {}
        
        while start < length:
            end = min(start + self.chunk_size, length)
            chunk_text = text[start:end]
            chunk_id = f"{doc_id}:{idx}"
            
            # Karakterpozíciók összefésülése a megadott dokumentum metaadataival
            metadata = {**base_metadata, "start": start, "end": end, "chunk_index": idx}
            
            chunks.append(Chunk(chunk_id=chunk_id, doc_id=doc_id, text=chunk_text, metadata=metadata))
            if end == length:
                break
            start = end - self.chunk_overlap
            idx += 1
        return chunks
