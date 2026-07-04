"""Uzun sureli hafiza: kullanici hakkinda kalici gercekler/tercihler.

Notlar'dan farki: notlar yapilacaklar listesi gibidir; profil ise Zenith'in
her sohbette hatirlamasi gereken kalici bilgilerdir (ismin, tercihlerin,
calistigin sey...). Her istekte system prompt'a enjekte edilir.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

MAX_FACTS = 50


def default_profile_path() -> Path:
    env_path = os.environ.get("ZENITH_PROFILE_PATH")
    if env_path:
        return Path(env_path)
    if os.environ.get("VERCEL"):
        return Path("/tmp/zenith-profile.json")
    return Path.home() / ".zenith" / "profile.json"


class ProfileStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_profile_path()
        self.facts: list[str] = self._load()

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.facts, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, fact: str) -> int:
        fact = fact.strip()
        if fact and fact not in self.facts:
            self.facts.append(fact)
            self.facts = self.facts[-MAX_FACTS:]
            self._save()
        return len(self.facts)

    def list(self) -> list[str]:
        return list(self.facts)

    def clear(self) -> None:
        self.facts = []
        self._save()

    def as_prompt(self) -> str:
        """Profili system prompt'a eklenecek metne cevirir; bos ise bos string."""
        if not self.facts:
            return ""
        lines = "\n".join(f"- {f}" for f in self.facts)
        return (
            "\n\nKullanici hakkinda hatirladiklarin (uygun oldugunda dikkate al, "
            f"gereksiz yere tekrar etme):\n{lines}"
        )
