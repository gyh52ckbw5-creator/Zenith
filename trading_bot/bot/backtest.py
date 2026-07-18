"""Backtest motoru: stratejiyi gecmis veri uzerinde, maliyetleri de
hesaba katarak calistirir.

Onemli durustluk kurallari:
- Sinyal mum KAPANISINDA uretilir, emir BIR SONRAKI mumun ACILISINDA
  gerceklesir (gelecegi gorme / look-ahead bias yok).
- Her islemde komisyon ve kayma (slippage) kesilir; gercek hayatta bunlar
  "karli" gorunen stratejilerin cogunu zarara cevirir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .data import Candle
from .strategies import Strategy


@dataclass
class Trade:
    entry_ts: int
    entry_price: float
    exit_ts: int = 0
    exit_price: float = 0.0
    pnl_pct: float = 0.0
    reason: str = "sinyal"  # sinyal | stop_loss | take_profit | trailing_stop | acik


@dataclass
class Result:
    strategy: str
    start_equity: float
    end_equity: float
    total_return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate_pct(self) -> float:
        closed = [t for t in self.trades if t.exit_ts]
        if not closed:
            return 0.0
        return 100.0 * sum(1 for t in closed if t.pnl_pct > 0) / len(closed)

    @property
    def profit_factor(self) -> float:
        """Toplam kar / toplam zarar. 1'in alti para kaybeder;
        saglam stratejilerde tipik olarak 1.3-2.0 arasi gorulur."""
        wins = sum(t.pnl_pct for t in self.trades if t.pnl_pct > 0)
        losses = abs(sum(t.pnl_pct for t in self.trades if t.pnl_pct < 0))
        if losses == 0:
            return float("inf") if wins > 0 else 0.0
        return wins / losses

    @property
    def sharpe(self) -> float:
        """Bar bazli getirilerden yillik varsayimsiz, kaba Sharpe orani."""
        rets = [
            self.equity_curve[i] / self.equity_curve[i - 1] - 1
            for i in range(1, len(self.equity_curve))
        ]
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        if std == 0:
            return 0.0
        return mean / std * math.sqrt(len(rets))

    def _bar_returns(self) -> list[float]:
        return [
            self.equity_curve[i] / self.equity_curve[i - 1] - 1
            for i in range(1, len(self.equity_curve))
            if self.equity_curve[i - 1]
        ]

    @property
    def sortino(self) -> float:
        """Sortino: Sharpe gibi ama SADECE asagi yonlu oynakligi cezalandirir.
        Yukari sicramalari 'risk' saymaz - daha adil bir risk-getiri olcusu."""
        rets = self._bar_returns()
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        downside = [r for r in rets if r < 0]
        if not downside:
            return float("inf") if mean > 0 else 0.0
        dd = math.sqrt(sum(r * r for r in downside) / len(downside))
        if dd == 0:
            return 0.0
        return mean / dd * math.sqrt(len(rets))

    @property
    def calmar(self) -> float:
        """Calmar: toplam getiri / maksimum dusus. Kazanci CANINI ne kadar
        yakarak elde ettigini soyler; >1 saglikli kabul edilir."""
        if self.max_drawdown_pct <= 0:
            return float("inf") if self.total_return_pct > 0 else 0.0
        return self.total_return_pct / self.max_drawdown_pct

    def summary(self) -> str:
        def fmt(x: float) -> str:
            return "sonsuz" if x == float("inf") else f"{x:.2f}"

        lines = [
            f"Strateji            : {self.strategy}",
            f"Baslangic bakiyesi  : {self.start_equity:,.2f}",
            f"Bitis bakiyesi      : {self.end_equity:,.2f}",
            f"Toplam getiri       : {self.total_return_pct:+.2f}%",
            f"Al-ve-tut getirisi  : {self.buy_hold_return_pct:+.2f}%  (kiyas)",
            f"Maksimum dusus (DD) : {self.max_drawdown_pct:.2f}%",
            f"Islem sayisi        : {self.n_trades}",
            f"Kazanma orani       : {self.win_rate_pct:.1f}%",
            f"Kar faktoru         : {self.profit_factor:.2f}",
            f"Sharpe (kaba)       : {fmt(self.sharpe)}",
            f"Sortino             : {fmt(self.sortino)}",
            f"Calmar (getiri/DD)  : {fmt(self.calmar)}",
        ]
        return "\n".join(lines)


def run_backtest(
    candles: list[Candle],
    strategy: Strategy,
    start_equity: float = 10_000.0,
    commission_pct: float = 0.1,
    slippage_pct: float = 0.05,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
    trailing_stop_pct: float = 0.0,
    cooldown_bars: int = 0,
    risk_pct_per_trade: float = 0.0,
    max_position_pct: float = 100.0,
) -> Result:
    """Stratejiyi calistirir. commission_pct/slippage_pct islem basina yuzdedir
    (0.1 = %0.1, tipik kripto spot komisyonu).

    stop_loss/take_profit/trailing_stop verilirse (0 = kapali) mum ICI
    tetiklenme simule edilir - canli botun risk davranisiyla ayni. Ayni mumda
    hem stop hem hedef vurulursa KOTUMSER varsayim: stop once sayilir.
    cooldown_bars: stop sonrasi bu kadar mum yeni giris yapilmaz (canli
    botun cooldown korumasiyla ayni).

    risk_pct_per_trade > 0 ise pozisyon boyutu canli botla ayni formulle
    hesaplanir: equity * risk / stop mesafesi; max_position_pct tavani
    uygulanir. Bu mod icin stop_loss_pct zorunludur. Varsayilan 0 eski
    "tum sermayeyle gir" davranisini korur.
    """
    if len(candles) < 2:
        raise ValueError("Backtest icin en az 2 mum gerekir")
    if start_equity <= 0:
        raise ValueError("start_equity pozitif olmali")
    if commission_pct < 0 or slippage_pct < 0:
        raise ValueError("komisyon ve slippage negatif olamaz")
    if stop_loss_pct < 0 or take_profit_pct < 0 or trailing_stop_pct < 0:
        raise ValueError("risk yuzdeleri negatif olamaz")
    if cooldown_bars < 0:
        raise ValueError("cooldown_bars negatif olamaz")
    if not (0 <= risk_pct_per_trade <= 5):
        raise ValueError("risk_pct_per_trade 0-5 araliginda olmali")
    if not (0 < max_position_pct <= 100):
        raise ValueError("max_position_pct 0-100 araliginda olmali")
    if risk_pct_per_trade > 0 and stop_loss_pct <= 0:
        raise ValueError("risk bazli pozisyon boyutu icin stop_loss_pct gerekli")

    targets = strategy.target_positions(candles)
    cost = (commission_pct + slippage_pct) / 100.0

    cash = start_equity
    units = 0.0
    trades: list[Trade] = []
    open_trade: Trade | None = None
    equity_curve: list[float] = []
    peak = start_equity
    max_dd = 0.0
    peak_price = 0.0  # iz suren stop icin pozisyondaki tepe fiyat
    cooldown = 0  # stop sonrasi kalan bekleme mumu

    def close_position(ts: int, fill: float, reason: str) -> None:
        nonlocal cash, units, open_trade
        cash += units * fill
        units = 0.0
        if open_trade:
            open_trade.exit_ts = ts
            open_trade.exit_price = fill
            open_trade.pnl_pct = 100.0 * (fill / open_trade.entry_price - 1)
            open_trade.reason = reason
            trades.append(open_trade)
            open_trade = None

    for i in range(len(candles)):
        c = candles[i]
        # i-1 kapanisindaki sinyal, i aciliginda islenir
        if i > 0 and targets[i - 1] != (1 if units > 0 else 0):
            if targets[i - 1] == 1 and cooldown == 0:  # al
                fill = c.open * (1 + cost)
                equity_before = cash
                allocation = equity_before * max_position_pct / 100.0
                if risk_pct_per_trade > 0:
                    by_risk = (
                        equity_before
                        * (risk_pct_per_trade / 100.0)
                        / (stop_loss_pct / 100.0)
                    )
                    allocation = min(allocation, by_risk)
                allocation = min(cash, allocation)
                units = allocation / fill
                cash -= allocation
                peak_price = fill
                open_trade = Trade(entry_ts=c.ts, entry_price=fill)
            elif targets[i - 1] == 0 and units > 0:  # sat
                close_position(c.ts, c.open * (1 - cost), "sinyal")
        if cooldown > 0:
            cooldown -= 1

        # mum ici stop / hedef kontrolleri (giris mumu dahil)
        if units > 0 and open_trade:
            entry = open_trade.entry_price
            peak_price = max(peak_price, c.high)
            stop = entry * (1 - stop_loss_pct / 100) if stop_loss_pct > 0 else 0.0
            trail = (
                peak_price * (1 - trailing_stop_pct / 100) if trailing_stop_pct > 0 else 0.0
            )
            tp = entry * (1 + take_profit_pct / 100) if take_profit_pct > 0 else 0.0
            if stop > 0 and c.low <= stop:  # kotumser: stop her seyden once
                # Fiyat stopun altinda acildiysa stop seviyesinden dolmak
                # imkansizdir; hafta sonu/haber gap'inde kotu acilisi kullan.
                raw_fill = min(c.open, stop)
                close_position(c.ts, raw_fill * (1 - cost), "stop_loss")
                cooldown = cooldown_bars
            elif trail > 0 and trail > stop and c.low <= trail:
                raw_fill = min(c.open, trail)
                close_position(c.ts, raw_fill * (1 - cost), "trailing_stop")
                cooldown = cooldown_bars
            elif tp > 0 and c.high >= tp:
                # Hedefin ustunde gap ile acilista piyasa daha iyi fiyati verir.
                raw_fill = max(c.open, tp)
                close_position(c.ts, raw_fill * (1 - cost), "take_profit")

        equity = cash + units * c.close
        equity_curve.append(equity)
        peak = max(peak, equity)
        max_dd = max(max_dd, 100.0 * (1 - equity / peak))

    if open_trade:  # acik pozisyonu son kapanistan degerle
        open_trade.exit_ts = candles[-1].ts
        open_trade.exit_price = candles[-1].close
        open_trade.pnl_pct = 100.0 * (candles[-1].close / open_trade.entry_price - 1)
        open_trade.reason = "acik"
        trades.append(open_trade)

    end_equity = equity_curve[-1]
    bh_return = 100.0 * (candles[-1].close / candles[1].open - 1)
    return Result(
        strategy=strategy.name,
        start_equity=start_equity,
        end_equity=end_equity,
        total_return_pct=100.0 * (end_equity / start_equity - 1),
        buy_hold_return_pct=bh_return,
        max_drawdown_pct=max_dd,
        trades=trades,
        equity_curve=equity_curve,
    )
