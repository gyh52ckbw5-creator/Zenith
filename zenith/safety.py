"""Güvenlik ve içerik filtreleme.

Zarar verici istekleri, jailbreak denemelerini ve uygunsuz içeriği
tespit eder.
"""

from __future__ import annotations

import re
from enum import Enum


class SafetyLevel(Enum):
    """İçerik güvenlik seviyeleri."""

    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"


class SafetyChecker:
    """Gelen istekleri ve çıkan cevapları kontrol eder."""

    # Jailbreak/zarar verici desen örnekleri
    DANGEROUS_PATTERNS = [
        r"ignore.*instructions",
        r"bypass.*filter",
        r"jailbreak",
        r"override.*restrictions",
        r"forget.*rules",
        r"disregard.*policy",
    ]

    # Spam/istismar desenleri
    SPAM_PATTERNS = [
        r"^(.)\1{20,}",  # Çok fazla tekrarlanan karakter
        r"\b\w{1}\b.*\b\w{1}\b",  # Çok kısa kelimeler
    ]

    def __init__(self):
        self.dangerous_re = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS]
        self.spam_re = [re.compile(p, re.IGNORECASE) for p in self.SPAM_PATTERNS]

    def check_input(self, user_input: str) -> tuple[SafetyLevel, str | None]:
        """Kullanıcı girdisini kontrol et."""
        if not user_input or len(user_input) > 10000:
            return SafetyLevel.WARNING, "Çok uzun veya boş bir giriş."

        # Jailbreak tespiti
        for pattern in self.dangerous_re:
            if pattern.search(user_input):
                return SafetyLevel.WARNING, "Potansiyel jailbreak denemesi algılandı."

        # Spam tespiti
        for pattern in self.spam_re:
            if pattern.search(user_input):
                return SafetyLevel.WARNING, "Spam benzeri bir giriş algılandı."

        return SafetyLevel.SAFE, None

    def check_output(self, response: str) -> tuple[SafetyLevel, str | None]:
        """Modelin çıktısını kontrol et."""
        if not response or len(response) > 50000:
            return SafetyLevel.WARNING, "Anormal yanıt boyutu."

        return SafetyLevel.SAFE, None
