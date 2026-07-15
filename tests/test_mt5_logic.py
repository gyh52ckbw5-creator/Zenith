"""MT5 koprusunun saf mantik katmani testleri (MetaTrader5 paketi gerekmez)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot import data  # noqa: E402
from bot.mt5_logic import decide, lot_from_risk, rates_to_candles, sl_tp_prices  # noqa: E402
from bot.risk import RiskConfig  # noqa: E402
from bot.strategies import BuyHold, SmaCross  # noqa: E402


def test_rates_to_candles_tuple():
    rates = [(1_700_000_000, 1.10, 1.12, 1.09, 1.11, 500),
             (1_700_000_060, 1.11, 1.13, 1.10, 1.12, 600)]
    candles = rates_to_candles(rates)
    assert len(candles) == 2
    assert candles[0].ts == 1_700_000_000_000  # saniye -> milisaniye
    assert candles[1].close == 1.12 and candles[0].volume == 500


def test_lot_from_risk_matches_ea_math():
    # equity 10000, risk %1 => 100$ risk. stop 2000 puan, point 0.00001,
    # tick_value=1, tick_size=0.00001 => loss_per_lot = 2000*0.00001/0.00001*1 = 2000
    # lots = 100/2000 = 0.05, step 0.01 => 0.05
    lots = lot_from_risk(10000, 2000, 0.00001, 1.0, 0.00001, 0.01, 0.01, 100.0, 1.0)
    assert abs(lots - 0.05) < 1e-9


def test_lot_from_risk_floors_and_bounds():
    assert lot_from_risk(100, 2000, 0.00001, 1.0, 0.00001, 0.01, 0.10, 100.0, 1.0) == 0.0  # minlot alti
    assert lot_from_risk(0, 2000, 0.00001, 1.0, 0.00001, 0.01, 0.01, 100.0, 1.0) == 0.0    # equity 0


def test_decide_buy_sell_hold():
    candles = data.synthetic(n=50, seed=1)
    # BuyHold hep 1 ister: pozisyon yokken 'buy', varken 'hold'
    assert decide(candles, False, BuyHold()) == "buy"
    assert decide(candles, True, BuyHold()) == "hold"
    assert decide(candles[:2], False, BuyHold()) == "hold"  # yetersiz veri


def test_decide_uses_closed_candle_only():
    # SmaCross ile: karar son (olusan) mumu ATLAR, kapanmislardan uretir
    candles = data.synthetic(n=300, seed=2)
    strat = SmaCross(10, 30)
    action = decide(candles, False, strat)
    assert action in ("buy", "hold")


def test_sl_tp_prices():
    sl, tp = sl_tp_prices(1.2000, RiskConfig(), 0.00001, 2000, 4000)
    assert abs(sl - 1.1800) < 1e-9 and abs(tp - 1.2400) < 1e-9
