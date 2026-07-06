"""RAG (Retrieval-Augmented Generation): kendi belgelerinle sohbet.

Ucretsiz ve anahtarsiz calisir: gomme (embedding) API'si yerine belgeleri
parcalara boler ve anahtar kelime ortakligina dayali (Jaccard benzeri) basit
bir puanlama ile en ilgili parcalari getirir. Kucuk-orta belgeler icin yeterli,
hicbir dis servise ihtiyac duymaz.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from math import log
from pathlib import Path

CHUNK_SIZE = 800  # karakter
CHUNK_OVERLAP = 150
TOP_K = 4
MAX_DOCS_CHARS = 200_000  # depo siniri (asiri buyume onlenir)

_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Turkce/Ingilizce cok sik gecen, ayirt edici olmayan kelimeler.
_STOPWORDS = {
    "ve", "ile", "bir", "bu", "da", "de", "mi", "ne", "icin", "gibi", "cok",
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "for", "on", "that",
}


def default_docs_path() -> Path:
    env_path = os.environ.get("ZENITH_DOCS_PATH")
    if env_path:
        return Path(env_path)
    if os.environ.get("VERCEL"):
        return Path("/tmp/zenith-docs.json")
    return Path.home() / ".zenith" / "docs.json"


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2 and t not in _STOPWORDS}


def _token_matches(q_token: str, c_tokens: set[str]) -> bool:
    """Turkce ekleri kabaca tolere etmek icin onek eslesmesi: 'kedi' <-> 'kediler'.
    Tam esitlik ya da >=4 karakterlik ortak onek yeterlidir."""
    if q_token in c_tokens:
        return True
    if len(q_token) >= 4:
        for ct in c_tokens:
            if ct.startswith(q_token) or q_token.startswith(ct) and len(ct) >= 4:
                return True
    return False


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


@dataclass
class Chunk:
    doc: str
    text: str


class DocStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_docs_path()
        self.chunks: list[dict] = self._load()

    def _load(self) -> list[dict]:
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
            json.dumps(self.chunks, ensure_ascii=False), encoding="utf-8"
        )

    def add_document(self, name: str, text: str) -> int:
        """Bir belgeyi parcalara bolup ekler. Eklenen parca sayisini dondurur."""
        pieces = chunk_text(text)
        for piece in pieces:
            self.chunks.append({"doc": name, "text": piece})
        # Depo cok buyurse en eski parcalari at.
        total = sum(len(c["text"]) for c in self.chunks)
        while total > MAX_DOCS_CHARS and self.chunks:
            removed = self.chunks.pop(0)
            total -= len(removed["text"])
        self._save()
        return len(pieces)

    def documents(self) -> list[str]:
        seen: list[str] = []
        for c in self.chunks:
            if c["doc"] not in seen:
                seen.append(c["doc"])
        return seen

    def clear(self) -> None:
        self.chunks = []
        self._save()

    def is_empty(self) -> bool:
        return not self.chunks

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[Chunk]:
        """TF-IDF benzeri agirlikli getirme: nadir (ayirt edici) kelimeler daha
        cok puan getirir; onek eslesmesi Turkce eklerini tolere eder."""
        q_tokens = _tokens(query)
        if not q_tokens or not self.chunks:
            return []

        # Her chunk'in jetonlarini bir kez hesapla + belge frekansi (DF).
        chunk_tokens = [_tokens(c["text"]) for c in self.chunks]
        n = len(self.chunks)
        df: dict[str, int] = {}
        for toks in chunk_tokens:
            for t in toks:
                df[t] = df.get(t, 0) + 1

        def idf(term: str) -> float:
            # Bir sorgu kelimesinin bir chunk kelimesiyle eslesen en yuksek IDF'i.
            best = 0.0
            for ct, count in df.items():
                if term == ct or (len(term) >= 4 and (ct.startswith(term) or term.startswith(ct))):
                    best = max(best, log((n + 1) / (count + 0.5)))
            return best

        q_idf = {qt: idf(qt) for qt in q_tokens}
        total = sum(q_idf.values()) or 1.0

        scored: list[tuple[float, dict]] = []
        for c, c_tokens in zip(self.chunks, chunk_tokens):
            if not c_tokens:
                continue
            score = sum(w for qt, w in q_idf.items() if _token_matches(qt, c_tokens))
            if score <= 0:
                continue
            scored.append((score / total, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [Chunk(doc=c["doc"], text=c["text"]) for _, c in scored[:top_k]]

    @staticmethod
    def format_context(chunks: list[Chunk]) -> str:
        return "\n\n".join(f"[{c.doc}] {c.text}" for c in chunks)
