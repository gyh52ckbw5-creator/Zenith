"""Otomatik arastirma/tarama motoru.

Birden fazla sembol x strateji x parametre kombinasyonunu tarar.
Veriyi ikiye boler:
  - egitim (in-sample): stratejinin "gordugu" gecmis
  - dogrulama (out-of-sample): stratejinin HIC gormedigi kisim

Siralama out-of-sample sonuca gore yapilir; in-sample'da parlak ama
dogrulamada coken kombinasyonlar "OVERFIT" olarak isaretlenir. Sosyal
medyadaki "bak gecmiste %500 yapmis" grafiklerinin panzehiri budur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .backtest import run_backtest
from .data import Candle
from .strategies import RsiReversion, SmaCross, Strategy


def default_grid() -> list[Strategy]:
    """Taranacak varsayilan strateji/parametre kombinasyonlari."""
    grid: list[Strategy] = []
    for fast, slow in [(10, 30), (20, 50), (50, 100), (20, 100)]:
        grid.append(SmaCross(fast, slow))
    for period, lo, hi in [(14, 30, 70), (7, 25, 75), (21, 35, 65)]:
        grid.append(RsiReversion(period, lo, hi))
    return grid


@dataclass
class ScanResult:
    symbol: str
    strategy: str
    train_return_pct: float
    test_return_pct: float
    test_buy_hold_pct: float
    test_max_dd_pct: float
    test_trades: int
    overfit: bool

    def row(self) -> str:
        flag = " OVERFIT!" if self.overfit else ""
        return (
            f"{self.symbol:<10} {self.strategy:<28} "
            f"egitim {self.train_return_pct:+7.2f}%  "
            f"dogrulama {self.test_return_pct:+7.2f}%  "
            f"(al-tut {self.test_buy_hold_pct:+.2f}%, DD {self.test_max_dd_pct:.1f}%, "
            f"{self.test_trades} islem){flag}"
        )


def scan(
    symbols: list[str],
    fetch: Callable[[str], list[Candle]],
    strategies: list[Strategy] | None = None,
    train_ratio: float = 0.7,
    commission_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> list[ScanResult]:
    """Tum kombinasyonlari calistirir, dogrulama getirisine gore siralar."""
    if not 0.5 <= train_ratio <= 0.9:
        raise ValueError("train_ratio 0.5-0.9 arasi olmali")
    strategies = strategies or default_grid()
    results: list[ScanResult] = []
    for symbol in symbols:
        candles = fetch(symbol)
        split = int(len(candles) * train_ratio)
        train, test = candles[:split], candles[split:]
        if len(train) < 120 or len(test) < 40:
            raise ValueError(f"{symbol}: tarama icin yeterli veri yok ({len(candles)} mum)")
        for strat in strategies:
            r_train = run_backtest(train, strat, commission_pct=commission_pct, slippage_pct=slippage_pct)
            r_test = run_backtest(test, strat, commission_pct=commission_pct, slippage_pct=slippage_pct)
            results.append(
                ScanResult(
                    symbol=symbol,
                    strategy=strat.name,
                    train_return_pct=r_train.total_return_pct,
                    test_return_pct=r_test.total_return_pct,
                    test_buy_hold_pct=r_test.buy_hold_return_pct,
                    test_max_dd_pct=r_test.max_drawdown_pct,
                    test_trades=r_test.n_trades,
                    overfit=r_train.total_return_pct > 5 and r_test.total_return_pct < 0,
                )
            )
    results.sort(key=lambda r: r.test_return_pct, reverse=True)
    return results


def best_pick(results: list[ScanResult]) -> ScanResult | None:
    """Overfit olmayan, dogrulamada artida kalan en iyi kombinasyon."""
    for r in results:
        if not r.overfit and r.test_return_pct > 0 and r.test_trades >= 2:
            return r
    return None
