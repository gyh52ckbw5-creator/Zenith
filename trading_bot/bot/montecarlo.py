"""Monte Carlo: bir backtest sonucu ne kadar SANSA baglıydi?

Tek backtest, islemlerin gercek sirasindan tek bir sonuc verir. Ama o sira
sans eseridir - ayni islemler baska sirayla gelseydi, ozellikle maksimum
dusus (drawdown) cok farkli olabilirdi. Monte Carlo, islem getirilerini
BINLERCE kez yeniden karistirip (bootstrap) sonuc DAGILIMINI cikarir:

  - Getirinin 5-50-95 yuzdelik araligi (kotu/orta/iyi sans)
  - Maksimum dususun dagilimi (en kotu senaryo ne kadar aci?)
  - Iflas olasiligi: kac simulasyonda hesap belli bir esigi geldi?

Boylece "gecmiste +%90 yapti" cumlesi yerine "sansa gore -%20 ile +%150
arasi, medyan +%60, ve %8 ihtimalle hesabin yarisini kaybederdin" gibi
DURUST bir tablo cikar. Fon yoneticilerinin standart araci budur.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass


@dataclass
class MonteCarloResult:
    trials: int
    n_trades: int
    return_p5: float
    return_p50: float
    return_p95: float
    maxdd_p50: float
    maxdd_p95: float   # kotu-sans drawdown (95. yuzdelik en derin)
    ruin_prob: float   # ruin_pct'yi asan simulasyon orani (0-1)
    ruin_pct: float

    def summary(self) -> str:
        return "\n".join([
            f"Monte Carlo ({self.trials} simulasyon, {self.n_trades} islem):",
            f"  Getiri araligi: kotu-sans (5%) {self.return_p5:+.1f}% | "
            f"medyan {self.return_p50:+.1f}% | iyi-sans (95%) {self.return_p95:+.1f}%",
            f"  Maksimum dusus: medyan %{self.maxdd_p50:.1f}, "
            f"kotu-sans (95%) %{self.maxdd_p95:.1f}",
            f"  Hesabin %{self.ruin_pct:.0f}'ini kaybetme ihtimali: %{100 * self.ruin_prob:.1f}",
            "  Not: Dar aralik = saglam sistem; genis aralik = sonuc buyuk olcude sansa bagli.",
        ])


def monte_carlo(
    trade_returns_pct: list[float],
    trials: int = 2000,
    seed: int = 42,
    ruin_pct: float = 50.0,
) -> MonteCarloResult | None:
    """Islem getirilerini (yuzde) yeniden ornekleyerek sonuc dagilimini cikarir.

    Bootstrap: her simulasyonda ayni sayida islem, gercek getirilerden
    YERINE KOYARAK secilir (sirayi ve olasi tekrarı simule eder).
    """
    trades = [r for r in trade_returns_pct if r == r]  # NaN ele
    n = len(trades)
    if n < 10:
        return None
    rng = random.Random(seed)
    finals: list[float] = []
    maxdds: list[float] = []
    ruined = 0
    for _ in range(trials):
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for _ in range(n):
            r = trades[rng.randrange(n)]
            equity *= 1 + r / 100.0
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, 100.0 * (1 - equity / peak))
        finals.append(100.0 * (equity - 1))
        maxdds.append(max_dd)
        if max_dd >= ruin_pct:
            ruined += 1
    finals.sort()
    maxdds.sort()

    def pct(data: list[float], p: float) -> float:
        i = min(len(data) - 1, max(0, int(round(p / 100.0 * (len(data) - 1)))))
        return data[i]

    return MonteCarloResult(
        trials=trials,
        n_trades=n,
        return_p5=pct(finals, 5),
        return_p50=statistics.median(finals),
        return_p95=pct(finals, 95),
        maxdd_p50=statistics.median(maxdds),
        maxdd_p95=pct(maxdds, 95),
        ruin_prob=ruined / trials,
        ruin_pct=ruin_pct,
    )
