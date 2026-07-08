"""Ornek stratejiler.

Bir strateji, her mum icin hedef pozisyon uretir:
  1 = long (varligi tut), 0 = nakitte kal.
Kisa (short) pozisyon bilerek yok: egitim amacli ve long-only tutulmustur.
"""

from __future__ import annotations

from .data import Candle
from .indicators import bollinger, ema, macd, rsi, sma


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


class EmaCross(Strategy):
    """SmaCross'un ussel ortalama versiyonu: son fiyatlara daha cabuk tepki
    verir, dolayisiyla daha erken girer ama daha cok yanlis sinyal uretir."""

    def __init__(self, fast: int = 12, slow: int = 26):
        if fast >= slow:
            raise ValueError("fast < slow olmali")
        self.fast, self.slow = fast, slow
        self.name = f"ema_cross({fast},{slow})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        closes = [c.close for c in candles]
        f, s = ema(closes, self.fast), ema(closes, self.slow)
        return [
            1 if f[i] is not None and s[i] is not None and f[i] > s[i] else 0
            for i in range(len(closes))
        ]


class DonchianBreakout(Strategy):
    """Donchian kanal kirilimi (klasik 'Turtle' trend takibi).

    Fiyat son `entry` mumun en yuksegini asarsa AL; son `exit` mumun
    en dusugunun altina inerse SAT. Trendleri sonuna kadar surer,
    yatay piyasada yanlis kirilimlarla zarar yazar.
    """

    def __init__(self, entry: int = 20, exit_: int = 10):
        if entry < 2 or exit_ < 2:
            raise ValueError("entry ve exit en az 2 olmali")
        self.entry, self.exit_ = entry, exit_
        self.name = f"donchian({entry},{exit_})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        out: list[int] = []
        pos = 0
        for i, c in enumerate(candles):
            if pos == 0 and i >= self.entry and c.close > max(highs[i - self.entry:i]):
                pos = 1
            elif pos == 1 and i >= self.exit_ and c.close < min(lows[i - self.exit_:i]):
                pos = 0
            out.append(pos)
        return out


class BuyHold(Strategy):
    """Kiyaslama olcutu: ilk mumda al, hic satma."""

    name = "buy_hold"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        return [1] * len(candles)


class BollingerReversion(Strategy):
    """Fiyat alt banda dokununca al, orta banda (SMA) donunce sat.

    Klasik ortalamaya donus: yatay/salinan piyasada calisir, guclu
    dusus trendinde arka arkaya erken giris yapabilir.
    """

    def __init__(self, period: int = 20, k: float = 2.0):
        self.period, self.k = period, k
        self.name = f"bollinger({period},{k:g})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        closes = [c.close for c in candles]
        mid, _, lower = bollinger(closes, self.period, self.k)
        out: list[int] = []
        pos = 0
        for i, c in enumerate(closes):
            if lower[i] is not None:
                if pos == 0 and c < lower[i]:
                    pos = 1
                elif pos == 1 and mid[i] is not None and c > mid[i]:
                    pos = 0
            out.append(pos)
        return out


class MacdCross(Strategy):
    """MACD cizgisi sinyal cizgisinin ustundeyken long, altindayken nakit."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast, self.slow, self.signal = fast, slow, signal
        self.name = f"macd({fast},{slow},{signal})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        closes = [c.close for c in candles]
        line, sig = macd(closes, self.fast, self.slow, self.signal)
        return [
            1 if line[i] is not None and sig[i] is not None and line[i] > sig[i] else 0
            for i in range(len(closes))
        ]


class TrendFilter(Strategy):
    """Baska bir stratejiyi sarmalar: fiyat uzun donem SMA'nin (varsayilan
    200) ustundeyken al sinyallerine izin verir, altindayken hepsini iptal
    eder. Dusus trendinde 'dusen bicagi tutma' islemlerini eler."""

    def __init__(self, base: Strategy, period: int = 200):
        self.base, self.period = base, period
        self.name = f"{base.name}+trend({period})"

    def target_positions(self, candles: list[Candle]) -> list[int]:
        base_pos = self.base.target_positions(candles)
        closes = [c.close for c in candles]
        trend = sma(closes, self.period)
        return [
            p if trend[i] is not None and closes[i] > trend[i] else 0
            for i, p in enumerate(base_pos)
        ]


STRATEGIES = {
    "sma": SmaCross,
    "ema": EmaCross,
    "rsi": RsiReversion,
    "donchian": DonchianBreakout,
    "bollinger": BollingerReversion,
    "macd": MacdCross,
    "hold": BuyHold,
}
