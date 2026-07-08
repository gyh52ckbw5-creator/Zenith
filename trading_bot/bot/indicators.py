"""Temel teknik indikatorler. Sonuc listeleri fiyat listesiyle ayni uzunluktadir;
henuz hesaplanamayan ilk degerler None olur."""

from __future__ import annotations


def sma(values: list[float], period: int) -> list[float | None]:
    """Basit hareketli ortalama."""
    out: list[float | None] = [None] * len(values)
    window_sum = 0.0
    for i, v in enumerate(values):
        window_sum += v
        if i >= period:
            window_sum -= values[i - period]
        if i >= period - 1:
            out[i] = window_sum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    """Ussel hareketli ortalama."""
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """Goreceli guc endeksi (Wilder yontemi), 0-100 arasi."""
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        gains += max(diff, 0)
        losses += max(-diff, 0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def bollinger(
    values: list[float], period: int = 20, k: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bollinger bantlari: (orta=SMA, ust, alt). k = standart sapma katsayisi."""
    mid = sma(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        mean = mid[i]
        std = (sum((v - mean) ** 2 for v in window) / period) ** 0.5
        upper[i] = mean + k * std
        lower[i] = mean - k * std
    return mid, upper, lower


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float | None], list[float | None]]:
    """MACD: (macd cizgisi, sinyal cizgisi). macd = EMA(fast) - EMA(slow)."""
    f, s = ema(values, fast), ema(values, slow)
    line: list[float | None] = [
        f[i] - s[i] if f[i] is not None and s[i] is not None else None
        for i in range(len(values))
    ]
    valid = [v for v in line if v is not None]
    sig_valid = ema(valid, signal)
    sig: list[float | None] = [None] * len(values)
    j = 0
    for i in range(len(values)):
        if line[i] is not None:
            sig[i] = sig_valid[j]
            j += 1
    return line, sig


def atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> list[float | None]:
    """Ortalama gercek aralik (ATR, Wilder): piyasanin oynaklik olcusu.

    Profesyonel kullanim: stop mesafesini sabit yuzde yerine ATR'nin
    kati olarak koymak - oynak piyasada genis, sakin piyasada dar stop.
    """
    n = len(closes)
    out: list[float | None] = [None] * n
    if n <= period:
        return out
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    prev = sum(trs[1 : period + 1]) / period
    out[period] = prev
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1 + avg_gain / avg_loss)
