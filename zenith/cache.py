"""Yanıt önbelleği ve hız optimizasyonu.

Sık sorulan sorulara hızlı cevap vermek için basit bellek içi ve
dosya tabanlı önbellek katmanı.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

CACHE_TTL_HOURS = 24


def default_cache_path() -> Path:
    """Önbellek dosyasının yolu."""
    env_path = os.environ.get("ZENITH_CACHE_PATH")
    if env_path:
        return Path(env_path)
    if os.environ.get("VERCEL"):
        return Path("/tmp/zenith-cache.json")
    return Path.home() / ".zenith" / "cache.json"


def _hash_query(query: str) -> str:
    """Soruyu hash'le (anahtar)."""
    return hashlib.md5(query.encode()).hexdigest()


class ResponseCache:
    """Yapay zeka cevaplarını ve araç sonuçlarını önbellekle."""

    def __init__(self, path: Path | None = None, ttl_hours: int = CACHE_TTL_HOURS):
        self.path = path or default_cache_path()
        self.ttl = timedelta(hours=ttl_hours)
        self.cache: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, query: str) -> str | None:
        """Sorguyu sorgula; geçerli ise cevabı döndür."""
        key = _hash_query(query)
        if key not in self.cache:
            return None
        entry = self.cache[key]
        try:
            saved_at = datetime.fromisoformat(entry.get("saved_at", ""))
            if datetime.now() - saved_at > self.ttl:
                del self.cache[key]
                self._save()
                return None
        except (ValueError, KeyError):
            return None
        return entry.get("response")

    def set(self, query: str, response: str) -> None:
        """Sorgu-cevap ikilisini önbellekle."""
        key = _hash_query(query)
        self.cache[key] = {
            "query": query,
            "response": response,
            "saved_at": datetime.now().isoformat(),
        }
        self._save()

    def clear(self) -> None:
        """Tüm önbelleği temizle."""
        self.cache = {}
        self._save()
