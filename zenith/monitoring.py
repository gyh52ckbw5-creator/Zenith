"""Sistem monitörü: sağlık kontrolü ve uyarılar.

Model kullanılabilirliğini, API sağlıklarını ve sistem durumunu takip eder.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime


@dataclass
class HealthCheck:
    """Bir modelin sağlık durumu."""

    model_name: str
    is_healthy: bool
    last_check: datetime
    error_message: str | None = None
    consecutive_failures: int = 0
    response_time_ms: float | None = None


class HealthMonitor:
    """Modellerin sağlığını sürekli izler."""

    def __init__(self, check_interval_seconds: int = 300):
        self.check_interval = check_interval_seconds
        self.health_status: dict[str, HealthCheck] = {}
        self.is_running = False

    async def start(self) -> None:
        """Monitor'u başlat."""
        self.is_running = True
        while self.is_running:
            await asyncio.sleep(self.check_interval)
            # Health checks burada çalışır

    def stop(self) -> None:
        """Monitor'u durdur."""
        self.is_running = False

    def get_status(self, model_name: str) -> HealthCheck | None:
        """Bir modelin son durumunu al."""
        return self.health_status.get(model_name)

    def get_healthy_models(self) -> list[str]:
        """Sağlıklı modelleri listele."""
        return [name for name, check in self.health_status.items() if check.is_healthy]
