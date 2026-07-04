"""Kalici notlar/hatirlaticilar. Zenith'in kullanici adina kucuk seyleri
hatirlamasini saglar. Hafiza gibi ortam-duyarli bir dosyada tutulur."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def default_notes_path() -> Path:
    env_path = os.environ.get("ZENITH_NOTES_PATH")
    if env_path:
        return Path(env_path)
    if os.environ.get("VERCEL"):
        return Path("/tmp/zenith-notes.json")
    return Path.home() / ".zenith" / "notes.json"


class NotesStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_notes_path()
        self.items: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, text: str) -> int:
        self.items.append({"text": text, "at": datetime.now().isoformat(timespec="minutes")})
        self._save()
        return len(self.items)

    def list(self) -> list[dict]:
        return list(self.items)

    def delete(self, index: int) -> bool:
        """1-tabanli indeks siler. Basariliysa True."""
        if 1 <= index <= len(self.items):
            self.items.pop(index - 1)
            self._save()
            return True
        return False

    def clear(self) -> None:
        self.items = []
        self._save()
