"""Islem gunlugu (trades_*.csv) analizi: gercek performans karnesi.

Backtest gecmis veriyi test eder; bu modul ise botun CANLI/paper modda
gercekten actigi islemleri okur ve durustce ozetler. Testnet koşusu
birikince "bot nasil gidiyor?" sorusunun sayisal cevabi burasidir.
"""

from __future__ import annotations

import csv
import glob
import os
from dataclasses import dataclass, field

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Stats:
    symbol: str
    n: int = 0
    wins: int = 0
    losses: int = 0
    pnl_sum: float = 0.0          # yuzde k/z toplami
    gross_win: float = 0.0        # kazanan islemlerin toplam yuzdesi
    gross_loss: float = 0.0       # kaybeden islemlerin toplam yuzdesi (pozitif)
    best: float = 0.0
    worst: float = 0.0
    by_reason: dict[str, int] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return 100.0 * self.wins / self.n if self.n else 0.0

    @property
    def expectancy(self) -> float:
        """Islem basina ortalama yuzde k/z - pozitif olmasi sarttir."""
        return self.pnl_sum / self.n if self.n else 0.0

    @property
    def profit_factor(self) -> float:
        if self.gross_loss == 0:
            return float("inf") if self.gross_win > 0 else 0.0
        return self.gross_win / self.gross_loss

    def row(self) -> str:
        pf = "inf" if self.profit_factor == float("inf") else f"{self.profit_factor:.2f}"
        reasons = ", ".join(f"{k}:{v}" for k, v in sorted(self.by_reason.items()))
        return (
            f"{self.symbol:<10} {self.n:>3} islem | kazanma %{self.win_rate:>5.1f} | "
            f"beklenti {self.expectancy:+.2f}% | kar faktoru {pf:>5} | "
            f"en iyi {self.best:+.1f}% en kotu {self.worst:+.1f}% | [{reasons}]"
        )


def analyze_csv(path: str) -> Stats:
    """Tek bir trades_SEMBOL.csv dosyasini ozetler."""
    symbol = os.path.basename(path).replace("trades_", "").replace(".csv", "")
    st = Stats(symbol=symbol)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                pnl = float(row["kz_yuzde"])
            except (KeyError, ValueError):
                continue  # bozuk satiri atla
            st.n += 1
            st.pnl_sum += pnl
            if pnl > 0:
                st.wins += 1
                st.gross_win += pnl
            elif pnl < 0:
                st.losses += 1
                st.gross_loss += -pnl
            st.best = max(st.best, pnl)
            st.worst = min(st.worst, pnl)
            reason = row.get("neden", "?") or "?"
            st.by_reason[reason] = st.by_reason.get(reason, 0) + 1
    return st


def analyze_all(base_dir: str = "") -> list[Stats]:
    base_dir = base_dir or _BASE
    files = sorted(glob.glob(os.path.join(base_dir, "trades_*.csv")))
    return [analyze_csv(p) for p in files]


def summary_text(base_dir: str = "") -> str:
    stats = analyze_all(base_dir)
    if not stats or all(s.n == 0 for s in stats):
        return (
            "Henuz kapanmis islem yok. Bot islem actikca trades_*.csv birikir; "
            "bu ozet o zaman anlam kazanir."
        )
    lines = ["Gercek islem karnesi (kapanmis islemlerden):"]
    tot = Stats(symbol="TOPLAM")
    for s in stats:
        if s.n == 0:
            continue
        lines.append("  " + s.row())
        tot.n += s.n
        tot.wins += s.wins
        tot.pnl_sum += s.pnl_sum
        tot.gross_win += s.gross_win
        tot.gross_loss += s.gross_loss
    if tot.n:
        lines.append("  " + "-" * 60)
        lines.append(
            f"  TOPLAM     {tot.n:>3} islem | kazanma %{tot.win_rate:>5.1f} | "
            f"beklenti {tot.expectancy:+.2f}% | kar faktoru "
            f"{('inf' if tot.profit_factor == float('inf') else f'{tot.profit_factor:.2f}')}"
        )
    verdict = (
        "Beklenti pozitif - strateji bu ornekte para KAZANDIRMIS (yine de gelecek garanti degil)."
        if tot.expectancy > 0
        else "Beklenti negatif/sifir - bu ornekte strateji KAZANDIRMAMIS. Ayarlari gozden gecir."
    )
    lines.append(verdict)
    lines.append("(Egitim amaclidir; gecmis performans gelecegi garanti etmez.)")
    return "\n".join(lines)
