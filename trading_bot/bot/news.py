"""Yuksek etkili ekonomik haber karantinasi.

Buyuk haberler (Fed karari, NFP, TUFE...) aciklanirken spread acilir,
fiyat sicrar ve stoplar kayarak (slippage) dolar. Profesyonel botlar bu
dakikalarda YENI pozisyon acmaz; acik pozisyonlar stop/hedefleriyle
yasamaya devam eder.

Kaynak: ForexFactory'nin ucretsiz haftalik takvimi (anahtar gerekmez).
Takvime ulasilamazsa sistem FAIL-OPEN calisir: karantina uygulanmaz,
bot durmaz - eksik veri, botu susturan bir bahane olmamali.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_CACHE: dict = {"ts": 0.0, "events": []}
_TTL_SEC = 6 * 3600  # takvim haftalik; 6 saatte bir tazelemek fazlasiyla yeterli

_KNOWN = ("EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "TRY", "CNY")


def fetch_events(force: bool = False) -> list[dict]:
    """Yuksek etkili olaylari [{ts, country, title}] olarak dondurur (onbellekli)."""
    if not force and time.time() - _CACHE["ts"] < _TTL_SEC:
        return _CACHE["events"]
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = json.loads(resp.read().decode())
    events: list[dict] = []
    for e in raw:
        if e.get("impact") != "High":
            continue
        try:
            ts = datetime.fromisoformat(e["date"]).timestamp()
        except (KeyError, ValueError, TypeError):
            continue
        events.append({"ts": ts, "country": e.get("country", ""), "title": e.get("title", "")})
    _CACHE.update(ts=time.time(), events=events)
    return events


def symbol_currencies(symbol: str) -> set[str]:
    """Sembolu etkileyen para birimleri: BTCUSDT->USD, EURUSD->EUR+USD,
    XAUUSD->USD... Bilinmeyende USD varsayilir (dunyanin referans birimi)."""
    s = symbol.upper()
    currencies = {c for c in _KNOWN if c in s}
    if "USD" in s or s.endswith("USDT") or not currencies:
        currencies.add("USD")
    return currencies


def news_blackout(
    symbol: str,
    now: float | None = None,
    window_min: int = 30,
    events: list[dict] | None = None,
) -> tuple[bool, str]:
    """Sembol icin haber karantinasi var mi? (karantina, olay_adi) dondurur.

    Olayin `window_min` dakika oncesi ve sonrasi karantinadir.
    """
    now = now if now is not None else time.time()
    if events is None:
        try:
            events = fetch_events()
        except Exception:  # noqa: BLE001 - takvim yoksa fail-open
            return False, ""
    currencies = symbol_currencies(symbol)
    window = window_min * 60
    for e in events:
        if e["country"] in currencies and abs(e["ts"] - now) <= window:
            return True, f"{e['country']} {e['title']}"
    return False, ""
