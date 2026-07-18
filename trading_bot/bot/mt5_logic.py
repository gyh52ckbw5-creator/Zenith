"""MT5 koprusunun SAF mantik katmani (MetaTrader5 paketi gerekmez).

Emir gonderme/veri cekme MT5'e ozeldir ve sadece Windows'ta calisir; ama
karar mantigi (mum donusumu, sinyal, lot hesabi) platformdan bagimsizdir ve
burada test edilir. Boylece kopru koduna guvenmeden once beyni dogrulanmis olur.
"""

from __future__ import annotations

import math
import time

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
    if (
        equity <= 0
        or stop_points <= 0
        or point <= 0
        or tick_value <= 0
        or tick_size <= 0
        or volume_min < 0
        or volume_max <= 0
        or risk_pct <= 0
    ):
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
    cfg.validate()
    if entry <= 0 or point <= 0 or stop_points <= 0 or tp_points <= 0:
        raise ValueError("entry, point, stop_points ve tp_points pozitif olmali")
    sl = entry - stop_points * point
    tp = entry + tp_points * point
    return sl, tp


def spread_points(bid: float, ask: float, point: float) -> float:
    """Bid/ask farkini broker puani cinsinden dondurur.

    Gecersiz veya ters kotasyon guvenli tarafta kalmak icin sonsuz spread
    sayilir ve yeni emir engellenir.
    """
    if bid <= 0 or ask <= 0 or point <= 0 or ask < bid:
        return float("inf")
    return (ask - bid) / point


def tick_is_fresh(tick_time: float, *, now: float | None = None,
                  max_age_seconds: float = 30.0) -> bool:
    """Kotasyon yeni mi? Piyasa kapaliyken kalan eski tick ile emir verme."""
    if tick_time <= 0 or max_age_seconds <= 0:
        return False
    current = time.time() if now is None else now
    age = current - tick_time
    # Makine/broker saati arasindaki kucuk ileri farklarini tolere et.
    return -5.0 <= age <= max_age_seconds


def daily_loss_pct(day_start_equity: float, current_equity: float) -> float:
    """Gun basina gore yuzdesel dusus; gecersiz degerde sonsuz risk."""
    if day_start_equity <= 0 or current_equity < 0:
        return float("inf")
    return max(0.0, 100.0 * (1.0 - current_equity / day_start_equity))


def daily_loss_exceeded(day_start_equity: float, current_equity: float,
                        max_daily_loss_pct: float) -> bool:
    """Gunluk zarar esigi asildi mi? Esik pozitif olmak zorundadir."""
    if max_daily_loss_pct <= 0:
        raise ValueError("max_daily_loss_pct pozitif olmali")
    return daily_loss_pct(day_start_equity, current_equity) >= max_daily_loss_pct


def latest_closed_bar_ts(candles: list[Candle]) -> int:
    """Olusan son mumu atlayip en yeni kapanmis mumun zamanini dondurur."""
    return candles[-2].ts if len(candles) >= 2 else 0


def broker_stops_valid(entry: float, sl: float, tp: float, point: float,
                       stops_level_points: int) -> bool:
    """SL/TP brokerin minimum mesafe kuralini karsiliyor mu?"""
    if entry <= 0 or point <= 0 or not (sl < entry < tp):
        return False
    minimum = max(0, stops_level_points) * point
    return (entry - sl) + 1e-12 >= minimum and (tp - entry) + 1e-12 >= minimum


def margin_within_limit(required_margin: float, equity: float,
                        max_margin_pct: float) -> bool:
    """Tek yeni pozisyonun baglayabilecegi azami equity yuzdesi."""
    if required_margin < 0 or equity <= 0 or not (0 < max_margin_pct <= 100):
        return False
    return required_margin <= equity * max_margin_pct / 100.0


def weekend_entry_blocked(timestamp: float, friday_cutoff_utc: int = 18) -> bool:
    """Cuma kapanisina yakin ve hafta sonu yeni pozisyon acma."""
    if not (0 <= friday_cutoff_utc <= 23):
        raise ValueError("friday_cutoff_utc 0-23 araliginda olmali")
    t = time.gmtime(timestamp)
    return t.tm_wday >= 5 or (t.tm_wday == 4 and t.tm_hour >= friday_cutoff_utc)
