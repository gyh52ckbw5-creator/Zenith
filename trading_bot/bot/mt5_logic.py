"""MT5 koprusunun SAF mantik katmani (MetaTrader5 paketi gerekmez).

Emir gonderme/veri cekme MT5'e ozeldir ve sadece Windows'ta calisir; ama
karar mantigi (mum donusumu, sinyal, lot hesabi) platformdan bagimsizdir ve
burada test edilir. Boylece kopru koduna guvenmeden once beyni dogrulanmis olur.
"""

from __future__ import annotations

import math

from .data import Candle
from .risk import RiskConfig


def rates_to_candles(rates) -> list[Candle]:
    """MT5 copy_rates_* ciktisini (time,open,high,low,close,tick_volume,...)
    bizim Candle listemize cevirir. rates: numpy structured array veya
    dict/tuple dizisi olabilir."""
    out: list[Candle] = []
    for r in rates:
        try:  # numpy structured array veya dict
            t, o, h, l, c = r["time"], r["open"], r["high"], r["low"], r["close"]
            vol = r["tick_volume"] if "tick_volume" in r.dtype.names else 0
        except (TypeError, KeyError, AttributeError):  # duz tuple: (time,o,h,l,c,tickvol,...)
            t, o, h, l, c = r[0], r[1], r[2], r[3], r[4]
            vol = r[5] if len(r) > 5 else 0
        out.append(
            Candle(ts=int(t) * 1000, open=float(o), high=float(h),
                   low=float(l), close=float(c), volume=float(vol))
        )
    return out


def lot_from_risk(
    equity: float,
    stop_points: int,
    point: float,
    tick_value: float,
    tick_size: float,
    volume_step: float,
    volume_min: float,
    volume_max: float,
    risk_pct: float,
) -> float:
    """EA'daki LotsByRisk ile ayni matematik: stop yerse kayip = equity*risk%.
    Lot, borsanin volume_step'ine ASAGI yuvarlanir; sinirlar uygulanir."""
    if equity <= 0 or tick_value <= 0 or tick_size <= 0:
        return 0.0
    risk_money = equity * risk_pct / 100.0
    loss_per_lot = stop_points * point / tick_size * tick_value
    if loss_per_lot <= 0:
        return 0.0
    lots = risk_money / loss_per_lot
    if volume_step > 0:
        lots = math.floor(lots / volume_step + 1e-9) * volume_step
    return max(min(lots, volume_max), 0.0) if lots >= volume_min else 0.0


def decide(candles: list[Candle], in_position: bool, strategy) -> str:
    """Kapanmis mumlardan karar: 'buy' | 'sell' | 'hold'.

    Sinyal SADECE kapanmis mumdan uretilir (son, olusan mum atlanir) -
    canli botun look-ahead yasagiyla ayni.
    """
    if len(candles) < 3:
        return "hold"
    target = strategy.target_positions(candles[:-1])[-1]
    if target == 1 and not in_position:
        return "buy"
    if target == 0 and in_position:
        return "sell"
    return "hold"


def sl_tp_prices(entry: float, cfg: RiskConfig, point: float,
                 stop_points: int, tp_points: int) -> tuple[float, float]:
    """Long pozisyon icin (stop_loss, take_profit) fiyatlari."""
    sl = entry - stop_points * point
    tp = entry + tp_points * point
    return sl, tp
