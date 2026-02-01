"""Dokumentum-verziótár a tudástár betöltéséhez.

Tervezési indoklás:
- SRP: dokumentumverziók követése (doc_id -> version_hash) az inkrementális frissítésekhez.
- Tartósság: egyszerű JSON fájl; nagyobb mérethez SQLite/DB-re bővíthető.
- Atomikus írás: ideiglenes fájl + átnevezés a sérülések elkerülésére.

Miért ez a megoldás:
- Lehetővé teszi az inkrementális betöltést: csak a változott dokumentumokat indexeljük újra.
- Követi az életciklust: új, frissített, törölt.
- Minimális függőség (csak JSON + fájlrendszer).

Séma:
{
  "doc_id": {
    "version_hash": "abc123...",
    "last_indexed": "2026-01-11T12:34:56",
    "file_path": "docs/kb-data/guide.pdf",
    "chunk_count": 42
  }
}
"""
from __future__ import annotations
from pathlib import Path
import json
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class VersionStore:
    """Tartós tároló a dokumentumverziók követéséhez.
    
    Tervezési jegyzetek:
    - Egyszerűség kedvéért JSON-on keresztül tölt és ment.
    - Az atomikus írás megakadályozza a sérülést.
    - Egyfolyamatú használathoz szálbiztos (nincs többfolyamatos zárolás).
    """
    
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _load(self) -> None:
        """Load version data from disk."""
        if self.store_path.exists():
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded version store: {len(self._data)} documents")
            except Exception as e:
                logger.error(f"Failed to load version store: {e}")
                self._data = {}
        else:
            logger.info("Version store does not exist; starting fresh")
    
    def _save(self) -> None:
        """A verzióadatok lemezre mentése atomikusan."""
        try:
            # Először ideiglenes fájlba írunk
            with tempfile.NamedTemporaryFile("w", delete=False, dir=str(self.store_path.parent), encoding="utf-8") as tf:
                json.dump(self._data, tf, indent=2, ensure_ascii=False)
                tmp_path = tf.name
            
            # Atomikus átnevezés
            Path(tmp_path).replace(self.store_path)
            logger.debug(f"Saved version store: {len(self._data)} documents")
        except Exception as e:
            logger.error(f"Failed to save version store: {e}")
    
    def get_version(self, doc_id: str) -> Optional[str]:
        """Visszaadja a dokumentum version_hash értékét, vagy None-t, ha nincs követve."""
        entry = self._data.get(doc_id)
        return entry["version_hash"] if entry else None
    
    def has_changed(self, doc_id: str, new_hash: str) -> bool:
        """Ellenőrzi, hogy a dokumentum megváltozott-e (új vagy frissült).
        
        Returns:
            True, ha új vagy eltér a hash; False, ha változatlan.
        """
        old_hash = self.get_version(doc_id)
        return old_hash is None or old_hash != new_hash
    
    def update(self, doc_id: str, version_hash: str, file_path: str, chunk_count: int) -> None:
        """Frissíti egy dokumentum verzióinformációit."""
        self._data[doc_id] = {
            "version_hash": version_hash,
            "last_indexed": datetime.now(timezone.utc).isoformat(),
            "file_path": file_path,
            "chunk_count": chunk_count,
        }
        self._save()
    
    def remove(self, doc_id: str) -> None:
        """Eltávolít egy dokumentumot a verziókövetésből."""
        if doc_id in self._data:
            del self._data[doc_id]
            self._save()
    
    def get_all_doc_ids(self) -> list[str]:
        """Visszaadja az összes követett doc_id-t."""
        return list(self._data.keys())
    
    def clear(self) -> None:
        """Minden verzióadat törlése (teljes újraindexeléshez)."""
        self._data = {}
        self._save()
