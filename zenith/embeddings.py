"""Basit embedding ve benzerlik hesaplama (anahtarsız).

Memet benzeri İngilizcede TF-IDF benzeri puanlama ile semantik arama.
Büyük embedding modeller ve API'ler gerektirmez.
"""

from __future__ import annotations

import re
from collections import Counter
from math import log, sqrt


def _tokenize(text: str) -> list[str]:
    """Metni basit kelime jetikleri halinde böl."""
    text = text.lower()
    # Sözcükleri ayıkla (Türkçe/İngilizce destek)
    words = re.findall(r"\w+", text)
    # Durma kelimelerini filtrele
    stopwords = {
        "ve", "ile", "bir", "bu", "da", "de", "mi", "ne", "icin", "gibi",
        "the", "a", "an", "and", "or", "of", "to", "in", "is", "for",
    }
    return [w for w in words if len(w) > 2 and w not in stopwords]


def cosine_similarity(text1: str, text2: str) -> float:
    """İki metin arasında kosinüs benzerliğini hesapla (0-1)."""
    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    counter1 = Counter(tokens1)
    counter2 = Counter(tokens2)

    # Dot product
    dot_product = sum(counter1[token] * counter2[token] for token in counter1 if token in counter2)

    # Magnitudes
    mag1 = sqrt(sum(count ** 2 for count in counter1.values()))
    mag2 = sqrt(sum(count ** 2 for count in counter2.values()))

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot_product / (mag1 * mag2)


def find_similar_questions(query: str, questions: list[str], top_k: int = 3) -> list[tuple[str, float]]:
    """Sorgulanan soruya benzer soruları bul."""
    similarities = [(q, cosine_similarity(query, q)) for q in questions]
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]
