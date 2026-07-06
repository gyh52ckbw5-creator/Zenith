"""Ornek stratejiler.

Bir strateji, her mum icin hedef pozisyon uretir:
  1 = long (varligi tut), 0 = nakitte kal.
Kisa (short) pozisyon bilerek yok: egitim amacli ve long-only tutulmustur.
"""

from __future__ import annotations

from .data import Candle
from .indicators import rsi, sma


class Strategy:
    name = "base"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        """Her mum kapanisinda istenen pozisyonu (0/1) dondurur."""
        raise NotImplementedError


class SmaCross(Strategy):
    """Hizli SMA yavas SMA'nin ustundeyken long, altindayken nakit.

    Klasik 'golden cross' trend takip stratejisi. Trendli piyasada iyi,
    yatay piyasada testere gibi zarar yazar - bunu backtestte kendin gor.
    """

    def __init__(self, fast: int = 20, slow: int = 50):
        if fast >= slow:
            raise ValueError("fast < slow olmali")
        self.fast, self.slow = fast, slow
        self.name = f"sma_cross({fast},{slow})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        closes = [c.close for c in candles]
        f, s = sma(closes, self.fast), sma(closes, self.slow)
        return [
            1 if f[i] is not None and s[i] is not None and f[i] > s[i] else 0
            for i in range(len(closes))
        ]


class RsiReversion(Strategy):
    """RSI asiri satimda (oversold) alir, asiri alimda (overbought) satar.

    Ortalamaya donus stratejisi: yatay piyasada calisir, guclu dususte
    'dusen bicagi tutma' riski tasir.
    """

    def __init__(self, period: int = 14, buy_below: float = 30, sell_above: float = 70):
        self.period, self.buy_below, self.sell_above = period, buy_below, sell_above
        self.name = f"rsi_reversion({period},{buy_below:g},{sell_above:g})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        closes = [c.close for c in candles]
        r = rsi(closes, self.period)
        out: list[int] = []
        pos = 0
        for v in r:
            if v is not None:
                if pos == 0 and v < self.buy_below:
                    pos = 1
                elif pos == 1 and v > self.sell_above:
                    pos = 0
            out.append(pos)
        return out


class BuyHold(Strategy):
    """Kiyaslama olcutu: ilk mumda al, hic satma."""

    name = "buy_hold"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        return [1] * len(candles)


STRATEGIES = {
    "sma": SmaCross,
    "rsi": RsiReversion,
    "hold": BuyHold,
}
