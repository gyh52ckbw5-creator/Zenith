"""Mum formasyonlari: MT5'in tanidigi klasik donus/devam sinyalleri.

MT5'teki 'BullishBearish Engulfing/Harami, HangingMan Hammer, MorningEvening
Star, DarkCloud PiercingLine, BlackCrows WhiteSoldiers' gostergelerinin
Python karsiligi. Her fonksiyon mum listesi alir ve her bar icin sinyal
dondurur: +1 (yukari/bogaz), -1 (asagi/ayi), 0 (yok).

DURUST NOT: Formasyonlar tek basina zayif sinyallerdir; degerleri baglamda
(trend, seviye) artar. Burada filtre/teyit araci olarak kullanilirlar.
"""

from __future__ import annotations

from .data import Candle


def _body(c: Candle) -> float:
    return abs(c.close - c.open)


def _range(c: Candle) -> float:
    return max(c.high - c.low, 1e-12)


def _bull(c: Candle) -> bool:
    return c.close > c.open


def _bear(c: Candle) -> bool:
    return c.close < c.open


def engulfing(candles: list[Candle]) -> list[int]:
    """Yutan formasyon: govde onceki govdeyi tamamen yutar."""
    out = [0] * len(candles)
    for i in range(1, len(candles)):
        p, c = candles[i - 1], candles[i]
        if _bear(p) and _bull(c) and c.close >= p.open and c.open <= p.close:
            out[i] = 1
        elif _bull(p) and _bear(c) and c.open >= p.close and c.close <= p.open:
            out[i] = -1
    return out


def harami(candles: list[Candle]) -> list[int]:
    """Harami: kucuk govde, onceki buyuk govdenin ICINDE (donus adayi)."""
    out = [0] * len(candles)
    for i in range(1, len(candles)):
        p, c = candles[i - 1], candles[i]
        inside = max(c.open, c.close) <= max(p.open, p.close) and \
            min(c.open, c.close) >= min(p.open, p.close)
        if not inside or _body(p) < _range(p) * 0.5:
            continue
        if _bear(p) and _bull(c):
            out[i] = 1
        elif _bull(p) and _bear(c):
            out[i] = -1
    return out


def hammer_hanging(candles: list[Candle]) -> list[int]:
    """Cekic (+1, dusus sonrasi) / Asili Adam (-1, yukselis sonrasi):
    kucuk govde ustte, uzun alt fitil (govdenin 2 kati+)."""
    out = [0] * len(candles)
    for i in range(3, len(candles)):
        c = candles[i]
        body = _body(c)
        lower_wick = min(c.open, c.close) - c.low
        upper_wick = c.high - max(c.open, c.close)
        if body < _range(c) * 0.35 and lower_wick >= 2 * body and upper_wick <= body:
            downtrend = c.low < min(x.low for x in candles[i - 3:i])
            uptrend = c.high > max(x.high for x in candles[i - 3:i])
            if downtrend:
                out[i] = 1   # cekic: dususte dip sinyali
            elif uptrend:
                out[i] = -1  # asili adam: yukseliste tepe uyarisi
    return out


def star_doji(candles: list[Candle]) -> list[int]:
    """Sabah Yildizi (+1) / Aksam Yildizi (-1), ortada doji/kucuk govde."""
    out = [0] * len(candles)
    for i in range(2, len(candles)):
        a, b, c = candles[i - 2], candles[i - 1], candles[i]
        if _body(b) > _range(b) * 0.3:  # orta mum kucuk/doji olmali
            continue
        if _bear(a) and _bull(c) and c.close > (a.open + a.close) / 2:
            out[i] = 1
        elif _bull(a) and _bear(c) and c.close < (a.open + a.close) / 2:
            out[i] = -1
    return out


def piercing_darkcloud(candles: list[Candle]) -> list[int]:
    """Delen Formasyon (+1) / Kara Bulut (-1): govdenin yarisini gecen donus."""
    out = [0] * len(candles)
    for i in range(1, len(candles)):
        p, c = candles[i - 1], candles[i]
        mid = (p.open + p.close) / 2
        if _bear(p) and _bull(c) and c.open <= p.close and mid < c.close < p.open:
            out[i] = 1
        elif _bull(p) and _bear(c) and c.open >= p.close and p.open < c.close < mid:
            out[i] = -1
    return out


def soldiers_crows(candles: list[Candle]) -> list[int]:
    """Uc Beyaz Asker (+1) / Uc Kara Karga (-1): ust uste 3 kararli mum."""
    out = [0] * len(candles)
    for i in range(2, len(candles)):
        trio = candles[i - 2:i + 1]
        if all(_bull(c) and _body(c) > _range(c) * 0.5 for c in trio) and \
                trio[0].close < trio[1].close < trio[2].close:
            out[i] = 1
        elif all(_bear(c) and _body(c) > _range(c) * 0.5 for c in trio) and \
                trio[0].close > trio[1].close > trio[2].close:
            out[i] = -1
    return out


ALL_PATTERNS = {
    "yutan": engulfing,
    "harami": harami,
    "cekic": hammer_hanging,
    "yildiz": star_doji,
    "delen": piercing_darkcloud,
    "askerler": soldiers_crows,
}


def scan_patterns(candles: list[Candle], lookback: int = 5) -> list[tuple[str, str, int]]:
    """Son `lookback` mumdaki formasyonlari dondurur: (isim, yon, kacinci_mum)."""
    found: list[tuple[str, str, int]] = []
    n = len(candles)
    for name, fn in ALL_PATTERNS.items():
        signals = fn(candles)
        for i in range(max(0, n - lookback), n):
            if signals[i] != 0:
                found.append((name, "yukari" if signals[i] > 0 else "asagi", n - 1 - i))
    return found


def pattern_report(candles: list[Candle], symbol: str) -> str:
    """Son mumlardaki formasyonlarin okunur ozeti."""
    found = scan_patterns(candles)
    if not found:
        return f"{symbol}: son mumlarda belirgin formasyon yok."
    lines = [f"{symbol} mum formasyonlari (son 5 mum):"]
    for name, direction, ago in sorted(found, key=lambda x: x[2]):
        when = "son mumda" if ago == 0 else f"{ago} mum once"
        arrow = "yukari donus" if direction == "yukari" else "asagi donus"
        lines.append(f"  {name}: {arrow} sinyali, {when}")
    lines.append("(Formasyonlar tek basina zayiftir; trend ve seviyeyle teyit gerekir.)")
    return "\n".join(lines)
