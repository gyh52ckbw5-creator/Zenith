"""Fiyat verisi kaynaklari: CSV, sentetik veri ve Binance halka acik API."""

from __future__ import annotations

import csv
import json
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """Tek bir mum (OHLCV) verisi."""

    ts: int  # unix milisaniye
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_csv(path: str) -> list[Candle]:
    """`ts,open,high,low,close,volume` baslikli bir CSV dosyasini yukler."""
    candles: list[Candle] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            candles.append(
                Candle(
                    ts=int(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0) or 0),
                )
            )
    return candles


def save_csv(path: str, candles: list[Candle]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ts", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow([c.ts, c.open, c.high, c.low, c.close, c.volume])


def synthetic(n: int = 1000, seed: int = 42, start_price: float = 100.0) -> list[Candle]:
    """Rejim degistiren (trend/yatay) sentetik fiyat serisi uretir.

    Gercek veri olmadan strateji ve backtest kodunu denemek icindir.
    """
    rng = random.Random(seed)
    candles: list[Candle] = []
    price = start_price
    drift = 0.0
    for i in range(n):
        if i % 120 == 0:  # her 120 mumda bir rejim degistir
            drift = rng.choice([-0.0008, 0.0, 0.0008, 0.0015])
        ret = rng.gauss(drift, 0.012)
        open_ = price
        close = max(0.01, price * (1 + ret))
        high = max(open_, close) * (1 + abs(rng.gauss(0, 0.003)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, 0.003)))
        candles.append(
            Candle(
                ts=1_700_000_000_000 + i * 3_600_000,
                open=round(open_, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=round(abs(rng.gauss(1000, 300)), 2),
            )
        )
        price = close
    return candles


_YAHOO_RANGE = {"1m": "5d", "5m": "1mo", "15m": "1mo", "30m": "3mo", "1h": "730d", "1d": "10y"}


def yahoo_symbol(symbol: str) -> str:
    """Kullanici dostu sembolu Yahoo formatina cevirir.

    EURUSD -> EURUSD=X (forex), XAUUSD/GOLD/ALTIN -> GC=F (altin vadeli),
    zaten Yahoo formatinda olanlar aynen gecer.
    """
    s = symbol.upper()
    if s in ("XAUUSD", "GOLD", "ALTIN"):
        return "GC=F"
    if s in ("XAGUSD", "SILVER", "GUMUS"):
        return "SI=F"
    if "=" in s or "." in s or "-" in s or "^" in s:
        return s
    if len(s) == 6 and s.isalpha() and not s.endswith("USDT"):
        return s + "=X"  # EURUSD, USDTRY, GBPUSD gibi forex pariteleri
    return s


def fetch_yahoo(symbol: str, interval: str = "1d", limit: int = 500) -> list[Candle]:
    """Yahoo Finance grafik API'sinden OHLC ceker (anahtar gerekmez).

    Forex (EURUSD=X), altin (GC=F), hisse, endeks - MT5'te gordugun USD
    paritelerinin verisi. Sadece VERI OKUR, islem yapamaz.
    """
    interval = {"4h": "1h"}.get(interval, interval)  # Yahoo 4h bilmez; 1h'e dusulur
    if interval not in _YAHOO_RANGE:
        raise ValueError(
            f"Yahoo {interval} desteklemiyor; secenekler: {', '.join(_YAHOO_RANGE)}"
        )
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval={interval}&range={_YAHOO_RANGE[interval]}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    return parse_yahoo(payload)[-limit:]


def parse_yahoo(payload: dict) -> list[Candle]:
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        err = payload.get("chart", {}).get("error")
        raise ValueError(f"Yahoo veri dondurmedi: {err}")
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    candles: list[Candle] = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c):  # Yahoo tatil/bos barlarda null doner
            continue
        vol = quote.get("volume", [0] * len(timestamps))[i] or 0
        candles.append(Candle(ts=int(ts) * 1000, open=o, high=h, low=l, close=c, volume=vol))
    return candles


def fetch_binance(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> list[Candle]:
    """Binance'in halka acik kline API'sinden veri ceker (API anahtari gerekmez).

    Sadece VERI OKUR; hesap/emir islemi yapmaz. Ag erisimi yoksa hata firlatir,
    bu durumda `synthetic()` veya CSV kullanin.
    """
    query = f"/api/v3/klines?symbol={symbol}&interval={interval}&limit={min(limit, 1000)}"
    last_err: Exception | None = None
    raw = None
    # binance.com bazi ulkelerden (ornegin ABD) 451 dondurur; binance.us yedek
    for host in ("api.binance.com", "api.binance.us"):
        try:
            with urllib.request.urlopen(f"https://{host}{query}", timeout=15) as resp:
                raw = json.loads(resp.read().decode())
            break
        except Exception as e:  # noqa: BLE001 - siradaki hosta gec
            last_err = e
    if raw is None:
        raise ConnectionError(
            f"Binance verisi cekilemedi ({last_err}). "
            "--source synthetic veya --source csv kullanin."
        )
    return [
        Candle(
            ts=int(k[0]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
            volume=float(k[5]),
        )
        for k in raw
    ]
