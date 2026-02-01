"""Fájlszkenner a tudástár betöltéséhez.

Tervezési indoklás:
- SRP: ennek a modulnak egyetlen feladata a KB mappában lévő fájlok felderítése
  és stabil azonosítók (doc_id, version_hash) számítása a változások felismeréséhez.
- Determinisztikus: a fájl hash (SHA256) megbízhatóan jelzi a tartalmi változást.
- Tesztelhető: tiszta függvények kapnak útvonalakat és metaadatot adnak vissza; nincs mellékhatás.

Miért hashing:
- Lehetővé teszi az inkrementális frissítést: csak a változott dokumentumokat indexeljük újra.
- Futások között stabil: azonos fájltartalom => azonos hash => nincs újraindexelés.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import hashlib
import logging

logger = logging.getLogger(__name__)


def compute_file_hash(path: Path) -> str:
    """SHA256 hash számítása a fájltartalomhoz verziódetektáláshoz.
    
    Miért SHA256: erős ütközésállóság, széles körű támogatás, elég gyors
    tipikus KB dokumentumokhoz (PDF-ek általában < 10MB).
    """
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()


def scan_kb_folder(kb_dir: Path, extensions: List[str] = None) -> List[Dict[str, Any]]:
    """Beolvassa a tudástár mappát és metaadatot ad vissza minden talált fájlhoz.
    
    Args:
        kb_dir: Útvonal a tudástár adatkönyvtárhoz
        extensions: Fájlkiterjesztések listája (pl. [".pdf", ".txt", ".md"]);
                   ha None, alapértelmezés [".pdf", ".txt", ".md"]
    
    Returns:
        Dict-ek listája a következő kulcsokkal: doc_id, file_path, version_hash, file_size, extension
    
    Tervezési jegyzetek:
    - A doc_id a relatív útvonalból származik (stabil marad a kb-data-n belüli mozgatásoknál)
    - A version_hash segít felismerni a fájlfrissítéseket
    - Felfedezési statisztikákat naplózunk az átláthatóságért
    """
    if extensions is None:
        extensions = [".pdf", ".txt", ".md"]
    
    if not kb_dir.exists():
        logger.warning(f"KB folder does not exist: {kb_dir}")
        return []
    
    discovered = []
    for ext in extensions:
        for fpath in kb_dir.rglob(f"*{ext}"):
            if not fpath.is_file():
                continue
            
            # doc_id származtatása a relatív útvonalból ("/" helyett "_")
            # Miért: stabil azonosító; engedi a dokumentumok almappákba rendezését
            relative = fpath.relative_to(kb_dir)
            doc_id = str(relative).replace("/", "_").replace("\\", "_")
            
            version_hash = compute_file_hash(fpath)
            
            discovered.append({
                "doc_id": doc_id,
                "file_path": str(fpath),
                "version_hash": version_hash,
                "file_size": fpath.stat().st_size,
                "extension": ext,
            })
    
    logger.info(f"Scanned {kb_dir}: found {len(discovered)} documents")
    return discovered
