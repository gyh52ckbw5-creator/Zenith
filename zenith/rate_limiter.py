"""Hız sınırlandırma (rate limiting) ve istismar koruması.

Sağlayıcı rate limitlerinden korunmak ve dönem başına istek sayısını
kontrol etmek için basit bir mekanizma.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class RateLimitConfig:
    """Her sağlayıcı için rate limit yapılandırması."""

    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    max_concurrent: int = 5


@dataclass
class RequestTracker:
    """Zaman penceresinde istekleri izler."""

    config: RateLimitConfig
    minute_requests: deque = field(default_factory=deque)
    hour_requests: deque = field(default_factory=deque)
    current_concurrent: int = 0

    def _cleanup(self) -> None:
        """Eski istekleri kaldır."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        while self.minute_requests and self.minute_requests[0] < minute_ago:
            self.minute_requests.popleft()
        while self.hour_requests and self.hour_requests[0] < hour_ago:
            self.hour_requests.popleft()

    def can_request(self) -> bool:
        """İstek yapabilir mi?"""
        self._cleanup()
        if len(self.minute_requests) >= self.config.max_requests_per_minute:
            return False
        if len(self.hour_requests) >= self.config.max_requests_per_hour:
            return False
        if self.current_concurrent >= self.config.max_concurrent:
            return False
        return True

    def record_request(self) -> None:
        """İsteği kaydet."""
        now = time.time()
        self.minute_requests.append(now)
        self.hour_requests.append(now)
        self.current_concurrent += 1

    def release_request(self) -> None:
        """İsteği tamamla."""
        self.current_concurrent = max(0, self.current_concurrent - 1)

    def wait_time_seconds(self) -> float:
        """Kaç saniye beklememiz gerekiyor?"""
        self._cleanup()
        if self.minute_requests:
            oldest = self.minute_requests[0]
            wait = 60 - (time.time() - oldest)
            if wait > 0:
                return wait
        return 0


class RateLimiter:
    """Çoklu sağlayıcı için hız sınırlandırması."""

    def __init__(self):
        self.trackers: dict[str, RequestTracker] = {}

    def get_tracker(self, provider: str, config: RateLimitConfig | None = None) -> RequestTracker:
        """Bir sağlayıcı için tracker'ı al veya oluştur."""
        if provider not in self.trackers:
            self.trackers[provider] = RequestTracker(config or RateLimitConfig())
        return self.trackers[provider]

    def can_request(self, provider: str) -> bool:
        """Bu sağlayıcıya istek yapabilir mi?"""
        return self.get_tracker(provider).can_request()

    def record(self, provider: str) -> None:
        """İsteği kaydet."""
        self.get_tracker(provider).record_request()

    def release(self, provider: str) -> None:
        """İsteği tamamla."""
        self.get_tracker(provider).release_request()

    def wait_time(self, provider: str) -> float:
        """Bekleme süresi (saniye)."""
        return self.get_tracker(provider).wait_time_seconds()
