"""Önbellek testleri."""

from __future__ import annotations

import pytest
from pathlib import Path
from zenith.cache import ResponseCache


@pytest.fixture
def cache(tmp_path: Path) -> ResponseCache:
    """Geçici bir cache oluştur."""
    return ResponseCache(path=tmp_path / "cache.json")


def test_cache_set_and_get(cache: ResponseCache) -> None:
    """Önbelleğe koy ve al."""
    query = "Test sorusu"
    response = "Test cevabı"

    cache.set(query, response)
    result = cache.get(query)

    assert result == response


def test_cache_miss(cache: ResponseCache) -> None:
    """Önbellek kaçırması."""
    result = cache.get("Var olmayan soru")
    assert result is None


def test_cache_clear(cache: ResponseCache) -> None:
    """Önbelleği temizle."""
    cache.set("Soru 1", "Cevap 1")
    cache.set("Soru 2", "Cevap 2")

    cache.clear()

    assert cache.get("Soru 1") is None
    assert cache.get("Soru 2") is None
