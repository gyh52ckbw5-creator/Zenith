"""trading_bot paketi icin testler."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot import data, indicators  # noqa: E402
from bot.backtest import run_backtest  # noqa: E402
from bot.strategies import BuyHold, RsiReversion, SmaCross  # noqa: E402


def test_synthetic_data_shape():
    candles = data.synthetic(n=300, seed=1)
    assert len(candles) == 300
    for c in candles:
        assert c.low <= min(c.open, c.close) <= max(c.open, c.close) <= c.high


def test_sma_basic():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = indicators.sma(vals, 3)
    assert out[:2] == [None, None]
    assert out[2] == 2.0 and out[4] == 4.0


def test_rsi_bounds():
    candles = data.synthetic(n=200, seed=2)
    r = indicators.rsi([c.close for c in candles], 14)
    computed = [v for v in r if v is not None]
    assert computed and all(0 <= v <= 100 for v in computed)


def test_backtest_buy_hold_matches_market():
    candles = data.synthetic(n=500, seed=3)
    res = run_backtest(candles, BuyHold(), commission_pct=0.0, slippage_pct=0.0)
    # Al-ve-tut, maliyetsiz kosumda piyasa getirisine esit olmali
    assert abs(res.total_return_pct - res.buy_hold_return_pct) < 1e-6
    assert res.n_trades == 1


def test_backtest_costs_reduce_returns():
    candles = data.synthetic(n=800, seed=4)
    strat = SmaCross(10, 30)
    free = run_backtest(candles, strat, commission_pct=0.0, slippage_pct=0.0)
    costly = run_backtest(candles, strat, commission_pct=0.25, slippage_pct=0.1)
    assert free.n_trades == costly.n_trades
    if free.n_trades > 0:
        assert costly.end_equity < free.end_equity


def test_no_lookahead_signal_executes_next_bar():
    # targets hep 1 olsa bile ilk islem 2. mumun ACILISINDA olmali
    candles = data.synthetic(n=50, seed=5)
    res = run_backtest(candles, BuyHold(), commission_pct=0.0, slippage_pct=0.0)
    assert res.trades[0].entry_ts == candles[1].ts
    assert res.trades[0].entry_price == candles[1].open


def test_backtest_position_cap_keeps_unallocated_cash():
    candles = [
        data.Candle(ts=1, open=100, high=100, low=100, close=100, volume=1),
        data.Candle(ts=2, open=100, high=100, low=100, close=100, volume=1),
        data.Candle(ts=3, open=110, high=110, low=110, close=110, volume=1),
    ]
    res = run_backtest(
        candles, BuyHold(), start_equity=10_000,
        commission_pct=0, slippage_pct=0, max_position_pct=25,
    )
    assert abs(res.end_equity - 10_250) < 1e-9
    assert abs(res.total_return_pct - 2.5) < 1e-9


def test_backtest_risk_position_sizing_matches_live_math():
    candles = [
        data.Candle(ts=1, open=100, high=100, low=100, close=100, volume=1),
        data.Candle(ts=2, open=100, high=100, low=100, close=100, volume=1),
        data.Candle(ts=3, open=110, high=110, low=110, close=110, volume=1),
    ]
    res = run_backtest(
        candles, BuyHold(), start_equity=10_000,
        commission_pct=0, slippage_pct=0,
        stop_loss_pct=2, risk_pct_per_trade=1, max_position_pct=100,
    )
    # 10,000 * %1 / %2 = 5,000 pozisyon; %10 fiyat artisi = 500 hesap kari.
    assert abs(res.end_equity - 10_500) < 1e-9
    assert abs(res.total_return_pct - 5.0) < 1e-9


def test_backtest_risk_sizing_requires_stop():
    with pytest.raises(ValueError, match="stop_loss_pct"):
        run_backtest(
            data.synthetic(n=10), BuyHold(),
            risk_pct_per_trade=1, stop_loss_pct=0,
        )


def test_rsi_strategy_runs():
    candles = data.synthetic(n=600, seed=6)
    res = run_backtest(candles, RsiReversion())
    assert len(res.equity_curve) == len(candles)
    assert res.max_drawdown_pct >= 0
