"""PDF parser a tudástár-betöltéshez.

Tervezési indoklás:
- SRP: a PDF feldolgozási logika elkülönítése; struktúrált adatot ad vissza (szöveg + metaadat).
- OCP: további parserrek (DOCX, HTML) is beilleszthetők egy interfésszel.
- Determinisztikus: oldalankénti kinyerés biztosítja a stabil darabolási támpontokat.

Miért pypdf:
- Tiszta Python, nincs külső függőség (ellentétben a pdfplumberrel vagy a camelottal).
- Elég a szövegkinyeréshez; a legtöbb PDF-fel jól működik.
- Könnyű és gyors.

Metaadat-megőrzés:
- Oldalszámok rögzítése hivatkozáshoz és kontextushoz.
- PDF metaadatok (cím, szerző) felvétele, ha elérhetők.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    logger.warning("pypdf not installed; PDF parsing disabled")
    PYPDF_AVAILABLE = False


class PDFParseResult:
    """Strukturált eredmény a PDF feldolgozásából.
    
    Miért osztály: a feldolgozott adatot és metaadatot is kapszulázza; könnyebb bővíteni.
    """
    def __init__(self, text: str, pages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self.text = text  # A teljes szöveg összefűzve
        self.pages = pages  # {page_num, text} elemek listája
        self.metadata = metadata  # PDF metaadatok (cím, szerző stb.)


def parse_pdf(file_path: Path) -> PDFParseResult:
    """PDF fájl feldolgozása és szöveg + metaadatok kinyerése.
    
    Args:
        file_path: Útvonal a PDF-hez
    
    Returns:
        PDFParseResult a szöveggel, oldal szintű adatokkal és PDF metaadatokkal
    
    Raises:
        RuntimeError: ha a pypdf nem érhető el
        Exception: ha a PDF nem dolgozható fel
    
    Tervezési jegyzetek:
    - Oldalankénti kinyerés lehetővé teszi az oldal-tudatos darabolást.
    - A metaadatkinyerés gazdagabb kontextust ad a visszakereséshez.
    """
    if not PYPDF_AVAILABLE:
        raise RuntimeError("pypdf not available; install via: pip install pypdf")
    
    try:
        reader = PdfReader(str(file_path))
        
        # PDF metaadatok kinyerése
        pdf_metadata = {}
        if reader.metadata:
            pdf_metadata = {
                "title": reader.metadata.get("/Title", ""),
                "author": reader.metadata.get("/Author", ""),
                "subject": reader.metadata.get("/Subject", ""),
                "creator": reader.metadata.get("/Creator", ""),
            }
        
        # Szöveg kinyerése oldalanként
        pages = []
        all_text = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            pages.append({
                "page_num": i + 1,  # 1-től indexelve, hogy embernek könnyebb legyen olvasni
                "text": page_text,
            })
            all_text.append(page_text)
        
        full_text = "\n".join(all_text)
        
        logger.info(f"Parsed PDF {file_path.name}: {len(reader.pages)} pages, {len(full_text)} chars")
        
        return PDFParseResult(
            text=full_text,
            pages=pages,
            metadata=pdf_metadata,
        )
    
    except Exception as e:
        logger.error(f"Failed to parse PDF {file_path}: {e}")
        raise
