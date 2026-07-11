"""Paranin matematigi: beklenti, Kelly kriteri, iflas olasiligi, korelasyon.

Iyi trader'i kumarbazdan ayiran sey strateji degil, boyutlandirma
matematigidir:

- BEKLENTI (expectancy): islem basina ortalama kazanc. Negatifse hicbir
  boyutlandirma seni kurtaramaz.
- KELLY: buyumeyi maksimize eden risk orani: f* = p - (1-p)/RR.
  TAM Kelly gercek hayatta fazla agresiftir (hesabin yarisini kaybetme
  olasiligi ~1/3); pratik standart YARIM Kelly'dir.
- IFLAS OLASILIGI (risk of ruin): mevcut risk ayarinla, seri kayiplarin
  seni oyun disi birakma ihtimalinin YAKLASIK degeri.
- KORELASYON: ayni yone giden iki enstrumana girmek cesitlendirme degil,
  ayni bahsi iki kez oynamaktir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class TradeStats:
    n: int
    win_rate: float        # 0-1
    avg_win_pct: float     # pozitif yuzde
    avg_loss_pct: float    # pozitif yuzde (mutlak)
    expectancy_pct: float  # islem basina beklenen yuzde
    rr: float              # odul/risk orani (avg_win/avg_loss)
    kelly: float           # onerilen tam Kelly orani (0-1)


def trade_stats(pnls_pct: list[float]) -> TradeStats | None:
    """Kapanan islem yuzdelerinden istatistik cikarir; islem yoksa None."""
    closed = [p for p in pnls_pct if p != 0]
    if not closed:
        return None
    wins = [p for p in closed if p > 0]
    losses = [-p for p in closed if p < 0]
    n = len(closed)
    p = len(wins) / n
    avg_w = sum(wins) / len(wins) if wins else 0.0
    avg_l = sum(losses) / len(losses) if losses else 0.0
    expectancy = p * avg_w - (1 - p) * avg_l
    rr = (avg_w / avg_l) if avg_l > 0 else float("inf")
    k = kelly_fraction(p, rr)
    return TradeStats(n=n, win_rate=p, avg_win_pct=avg_w, avg_loss_pct=avg_l,
                      expectancy_pct=expectancy, rr=rr, kelly=k)


def kelly_fraction(win_rate: float, rr: float) -> float:
    """Kelly kriteri: f* = p - (1-p)/RR. Negatifse 0 (oynama!)."""
    if rr <= 0 or not (0 <= win_rate <= 1):
        return 0.0
    if math.isinf(rr):
        return win_rate
    return max(0.0, win_rate - (1 - win_rate) / rr)


def risk_of_ruin(win_rate: float, rr: float, risk_pct: float, ruin_dd_pct: float = 50.0) -> float:
    """Iflas olasiligi YAKLASIMI (0-1): mevcut kazanma orani/odul-risk ile,
    islem basina risk_pct riskle, hesabin ruin_dd_pct'sini kaybetme ihtimali.

    Klasik kumarbaz iflasi yaklasimi: RoR = ((1-A)/(1+A))^U
      A = avantaj (Kelly benzeri kenar), U = iflasa kadar risk birimi sayisi.
    Kaba bir pusuladir, kehanet degil; egitim icin yeterli.
    """
    if risk_pct <= 0:
        return 0.0
    edge = kelly_fraction(win_rate, rr)
    if edge <= 0:
        return 1.0  # kenarin yoksa yeterince oynayan herkes iflas eder
    units = ruin_dd_pct / risk_pct
    base = (1 - edge) / (1 + edge)
    return min(1.0, base ** units)


def pct_returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1]]


def pearson(a: list[float], b: list[float]) -> float:
    """Pearson korelasyonu (-1..1). Uzunluklar sondan hizalanir."""
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    x, y = a[-n:], b[-n:]
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sx = math.sqrt(sum((v - mx) ** 2 for v in x))
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def format_stats(stats: TradeStats, current_risk_pct: float = 1.0) -> str:
    """Istatistikleri insan-okur Turkce ozete cevirir."""
    if stats.n < 10:
        return (
            f"Istatistik: {stats.n} islem - saglikli sonuc icin en az 10 gerekir, "
            "veri biriktirmeye devam."
        )
    half_kelly = 100 * stats.kelly / 2
    ror = risk_of_ruin(stats.win_rate, stats.rr, current_risk_pct)
    lines = [
        f"Istatistik ({stats.n} islem):",
        f"  Kazanma orani: %{100 * stats.win_rate:.1f} | ort. kazanc +%{stats.avg_win_pct:.2f} "
        f"| ort. kayip -%{stats.avg_loss_pct:.2f} (RR {stats.rr:.2f})",
        f"  Beklenti: islem basina %{stats.expectancy_pct:+.3f}"
        + (" - POZITIF, sistem kenar uretiyor" if stats.expectancy_pct > 0
           else " - NEGATIF: boyutlandirma bunu kurtaramaz, strateji masasina don"),
        f"  Kelly: tam %{100 * stats.kelly:.1f} -> onerilen YARIM Kelly ~%{half_kelly:.1f} "
        f"islem basina risk",
        f"  Iflas olasiligi (islem basina %{current_risk_pct:g} riskle, %50 kayba ulasma, "
        f"yaklasik): %{100 * ror:.2f}",
    ]
    return "\n".join(lines)
