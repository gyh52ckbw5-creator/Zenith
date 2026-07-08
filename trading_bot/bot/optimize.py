"""Parametre optimizasyonu - walk-forward puanlamali (hyperopt-lite).

Klasik tuzak: parametreleri tek gecmis donemde en iyi sonuca gore secmek
(overfitting). Burada her deneme WALK-FORWARD ile puanlanir:
veri ardisik dilimlere bolunur, aday parametre her dilimde ayri kosulur,
puan = dilim getirilerinin MEDYANI (siralamada esitlik bozucu: en kotu
dilim). Boylece tek donemin sansli kahramanlari degil, farkli piyasa
kosullarinda ayakta kalanlar one cikar.

Yine de unutma: en iyi aday bile GECMISE gore secildi. Canli oncesi
son soz her zaman taze (hic gorulmemis) veridedir.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from .data import Candle
from .scanner import walk_forward
from .strategies import (
    BollingerReversion,
    DonchianBreakout,
    EmaCross,
    MacdCross,
    RsiReversion,
    SmaCross,
    Strategy,
)


def sample_strategy(kind: str, rng: random.Random) -> Strategy:
    """Verilen strateji turu icin rastgele ama GECERLI bir parametre kombinasyonu."""
    if kind == "sma":
        fast = rng.randrange(5, 61)
        return SmaCross(fast, rng.randrange(fast + 10, 201))
    if kind == "ema":
        fast = rng.randrange(5, 41)
        return EmaCross(fast, rng.randrange(fast + 8, 121))
    if kind == "rsi":
        buy = rng.randrange(20, 36)
        return RsiReversion(rng.randrange(7, 29), buy, rng.randrange(65, 81))
    if kind == "donchian":
        entry = rng.randrange(10, 81)
        return DonchianBreakout(entry, rng.randrange(5, max(6, entry // 2 + 1)))
    if kind == "bollinger":
        return BollingerReversion(rng.randrange(10, 41), round(rng.uniform(1.5, 3.0), 1))
    if kind == "macd":
        fast = rng.randrange(8, 17)
        return MacdCross(fast, rng.randrange(fast + 8, 41), rng.randrange(6, 13))
    raise ValueError(f"optimizasyon icin bilinmeyen strateji: {kind}")


@dataclass
class OptResult:
    strategy: str
    median_pct: float   # dilim getirilerinin medyani (ana puan)
    worst_pct: float    # en kotu dilim (dayaniklilik gostergesi)
    segments: list[float]

    def row(self) -> str:
        segs = " ".join(f"{r:+6.1f}" for r in self.segments)
        return (
            f"{self.strategy:<28} medyan {self.median_pct:+7.2f}%  "
            f"en kotu {self.worst_pct:+7.2f}%  dilimler: [{segs}]"
        )


def optimize(
    candles: list[Candle],
    kind: str,
    trials: int = 30,
    segments: int = 5,
    seed: int = 42,
    commission_pct: float = 0.1,
    slippage_pct: float = 0.05,
    **risk_kwargs,
) -> list[OptResult]:
    """`trials` rastgele parametre dener, walk-forward puanina gore siralar."""
    rng = random.Random(seed)
    results: list[OptResult] = []
    seen: set[str] = set()
    for _ in range(trials):
        strat = sample_strategy(kind, rng)
        if strat.name in seen:  # ayni kombinasyonu bosuna tekrar kosma
            continue
        seen.add(strat.name)
        returns = walk_forward(
            candles, strat, segments=segments,
            commission_pct=commission_pct, slippage_pct=slippage_pct, **risk_kwargs,
        )
        results.append(
            OptResult(
                strategy=strat.name,
                median_pct=statistics.median(returns),
                worst_pct=min(returns),
                segments=returns,
            )
        )
    results.sort(key=lambda r: (r.median_pct, r.worst_pct), reverse=True)
    return results
