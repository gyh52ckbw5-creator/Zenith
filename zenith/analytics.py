"""Analitikler: kullanım istatistikleri ve performans izlemesi.

Kaç soru soruldu, hangi modeller kullanıldı, ortalama yanıt süresi, vb.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def default_analytics_path() -> Path:
    """Analitik dosyasının yolu."""
    env_path = os.environ.get("ZENITH_ANALYTICS_PATH")
    if env_path:
        return Path(env_path)
    if os.environ.get("VERCEL"):
        return Path("/tmp/zenith-analytics.json")
    return Path.home() / ".zenith" / "analytics.json"


@dataclass
class RequestStats:
    """İstek istatistikleri."""

    timestamp: str
    question_length: int
    response_length: int
    response_time_seconds: float
    model_used: str
    source: str  # "model", "council", "skill", "cache", etc.
    success: bool
    error_message: str | None = None


@dataclass
class AnalyticsData:
    """Toplam analitikler."""

    total_requests: int = 0
    total_questions: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    total_response_time_seconds: float = 0.0
    model_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    requests: list[RequestStats] = field(default_factory=list)

    def average_response_time(self) -> float:
        """Ortalama yanıt süresi (saniye)."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time_seconds / self.total_requests

    def success_rate(self) -> float:
        """Başarı oranı (0-1)."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class Analytics:
    """Kullanım istatistiklerini kaydet ve sorgulanabilir hale getir."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_analytics_path()
        self.data = self._load()

    def _load(self) -> AnalyticsData:
        if not self.path.exists():
            return AnalyticsData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return AnalyticsData(
                total_requests=raw.get("total_requests", 0),
                total_questions=raw.get("total_questions", 0),
                successful_requests=raw.get("successful_requests", 0),
                failed_requests=raw.get("failed_requests", 0),
                cache_hits=raw.get("cache_hits", 0),
                total_response_time_seconds=raw.get("total_response_time_seconds", 0.0),
                model_stats=raw.get("model_stats", {}),
            )
        except (json.JSONDecodeError, OSError):
            return AnalyticsData()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "total_requests": self.data.total_requests,
                    "total_questions": self.data.total_questions,
                    "successful_requests": self.data.successful_requests,
                    "failed_requests": self.data.failed_requests,
                    "cache_hits": self.data.cache_hits,
                    "total_response_time_seconds": self.data.total_response_time_seconds,
                    "model_stats": self.data.model_stats,
                    "last_updated": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def record(self, stats: RequestStats) -> None:
        """İstek istatistiklerini kaydet."""
        self.data.total_requests += 1
        self.data.total_questions += 1
        self.data.total_response_time_seconds += stats.response_time_seconds

        if stats.success:
            self.data.successful_requests += 1
        else:
            self.data.failed_requests += 1

        if stats.source == "cache":
            self.data.cache_hits += 1

        if stats.model_used not in self.data.model_stats:
            self.data.model_stats[stats.model_used] = {"requests": 0, "success": 0}

        self.data.model_stats[stats.model_used]["requests"] += 1
        if stats.success:
            self.data.model_stats[stats.model_used]["success"] += 1

        self.data.requests.append(stats)
        # Son 1000 isteği tut
        if len(self.data.requests) > 1000:
            self.data.requests = self.data.requests[-1000:]

        self._save()

    def summary(self) -> dict:
        """Özet istatistikler."""
        return {
            "total_requests": self.data.total_requests,
            "successful_requests": self.data.successful_requests,
            "failed_requests": self.data.failed_requests,
            "cache_hits": self.data.cache_hits,
            "success_rate": f"{self.data.success_rate() * 100:.1f}%",
            "average_response_time_seconds": f"{self.data.average_response_time():.2f}s",
            "model_stats": self.data.model_stats,
        }
