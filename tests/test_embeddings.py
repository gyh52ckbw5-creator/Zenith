"""Embedding testleri."""

from __future__ import annotations

import pytest
from zenith.embeddings import cosine_similarity, find_similar_questions


def test_cosine_similarity_identical() -> None:
    """Aynı metinler 1.0 benzerliğine sahip olmalı."""
    text = "Python programming language"
    similarity = cosine_similarity(text, text)
    assert similarity == pytest.approx(1.0, abs=0.01)


def test_cosine_similarity_different() -> None:
    """Farklı metinler düşük benzerliğe sahip olmalı."""
    text1 = "Merhaba dünya"
    text2 = "Hoşça kalın ay"
    similarity = cosine_similarity(text1, text2)
    assert 0 <= similarity < 0.5


def test_find_similar_questions() -> None:
    """Benzer soruları bul."""
    questions = [
        "Hava nasıl?",
        "İstanbul'da hava durumu nedir?",
        "Bugün kaç derece?",
    ]
    results = find_similar_questions("Hava durumu", questions, top_k=2)

    assert len(results) == 2
    assert all(score > 0 for _, score in results)
