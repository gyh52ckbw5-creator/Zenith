"""Yardımcı fonksiyonlar."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


def normalize_text(text: str) -> str:
    """Metni normalize et (boşluk, unicode vb.)."""
    # Unicode normalize et (çok-bayt -> tek bayt)
    text = unicodedata.normalize("NFKD", text)
    # Fazla boşlukları sil
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Metni belirtilen uzunluğa kısalt."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def hash_text(text: str, algorithm: str = "sha256") -> str:
    """Metni hash'le."""
    if algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(text.encode()).hexdigest()
    else:
        raise ValueError(f"Desteklenmeyen hash algoritması: {algorithm}")


def sanitize_filename(filename: str) -> str:
    """Dosya adını güvenli hale getir."""
    # Tehlikeli karakterleri kaldır
    filename = re.sub(r"[^\w\-. ]", "", filename)
    # Boşlukları altçizgi ile değiştir
    filename = re.sub(r"\s+", "_", filename)
    return filename[:255]  # Dosya adı maksimum uzunluğu


def merge_dicts(*dicts: dict[str, Any]) -> dict[str, Any]:
    """Birden fazla dict'i birleştir (sonuncusu kazanır)."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def format_size(size_bytes: int) -> str:
    """Dosya boyutunu okunabilir formata çevir."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"
