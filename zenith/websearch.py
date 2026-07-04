"""Ucretsiz web aramasi (DuckDuckGo, API anahtari gerektirmez).

Kullanici "ara: <sorgu>" yazdiginda Zenith once web'de arar, sonra bulgulari
modele verip guncel bilgiyle cevap urettirir.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

MAX_RESULTS = 5
REQUEST_TIMEOUT_SECONDS = 10  # serverless fonksiyon butcesini korur


class SearchError(RuntimeError):
    """Arama servisi ulasilamaz oldugunda firlatilir."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


def _search_sync(query: str, max_results: int) -> list[SearchResult]:
    from ddgs import DDGS

    try:
        raw = DDGS(timeout=REQUEST_TIMEOUT_SECONDS).text(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001 - ag/parse hatalari cesitli
        raise SearchError(f"Web aramasi basarisiz: {exc}") from exc

    return [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("href", ""),
            snippet=item.get("body", ""),
        )
        for item in raw
    ]


async def search(query: str, max_results: int = MAX_RESULTS) -> list[SearchResult]:
    """Aramayi thread'de calistirir; ddgs senkron bir kutuphanedir ve event
    loop'u bloklamamalidir."""
    return await asyncio.to_thread(_search_sync, query, max_results)


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "(arama sonucu bulunamadi)"
    return "\n\n".join(
        f"[{i + 1}] {r.title}\n{r.url}\n{r.snippet}" for i, r in enumerate(results)
    )
