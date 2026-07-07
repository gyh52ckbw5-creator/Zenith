"""Risk yonetimi, tarama motoru ve borsa imzasi testleri."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot import data  # noqa: E402
from bot.exchange import sign  # noqa: E402
from bot.risk import RiskConfig, daily_kill_switch, exit_reason, position_size_quote  # noqa: E402
from bot.scanner import best_pick, scan  # noqa: E402


def test_position_size_risk_math():
    # %1 risk, %2 stop => pozisyon sermayenin %50'si... ama %25 tavana takilir
    cfg = RiskConfig(risk_pct_per_trade=1.0, stop_loss_pct=2.0, max_position_pct=25.0)
    assert position_size_quote(10_000, cfg) == 2_500.0
    # tavansiz hali: 10000 * 0.01 / 0.02 = 5000
    cfg2 = RiskConfig(risk_pct_per_trade=1.0, stop_loss_pct=2.0, max_position_pct=100.0)
    assert position_size_quote(10_000, cfg2) == 5_000.0


def test_position_size_rejects_gambling():
    with pytest.raises(ValueError):
        RiskConfig(risk_pct_per_trade=50.0).validate()  # hesabin yarisini riske atmak yok


def test_exit_reason_stop_and_take_profit():
    cfg = RiskConfig(stop_loss_pct=2.0, take_profit_pct=4.0)
    assert exit_reason(100.0, 97.9, cfg) == "stop_loss"
    assert exit_reason(100.0, 104.1, cfg) == "take_profit"
    assert exit_reason(100.0, 101.0, cfg) is None


def test_daily_kill_switch():
    cfg = RiskConfig(max_daily_loss_pct=5.0)
    assert daily_kill_switch(10_000, 9_400, cfg) is True
    assert daily_kill_switch(10_000, 9_700, cfg) is False


def test_scan_ranks_by_out_of_sample():
    def fetch(symbol: str) -> list[data.Candle]:
        return data.synthetic(n=800, seed=abs(hash(symbol)) % 100)

    from bot.scanner import default_grid

    results = scan(["AAA", "BBB"], fetch)
    assert len(results) == 2 * len(default_grid())  # sembol sayisi x kombinasyon
    test_returns = [r.test_return_pct for r in results]
    assert test_returns == sorted(test_returns, reverse=True)


def test_best_pick_skips_overfit():
    def fetch(symbol: str) -> list[data.Candle]:
        return data.synthetic(n=800, seed=1)

    results = scan(["AAA"], fetch)
    pick = best_pick(results)
    if pick is not None:
        assert not pick.overfit
        assert pick.test_return_pct > 0
        assert pick.test_trades >= 2


def test_binance_signature_matches_reference():
    # Binance resmi dokumanindaki ornek anahtar/sorgu ile dogrulama
    secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
    query = (
        "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1"
        "&price=0.1&recvWindow=5000&timestamp=1499827319559"
    )
    assert sign(query, secret) == (
        "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
    )


def test_notify_silent_without_config(monkeypatch):
    from bot.notify import send_telegram, telegram_configured

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram_configured() is False
    assert send_telegram("test") is False  # yapilandirma yoksa sessizce False


def test_trader_state_path_per_symbol():
    from bot.trader import state_path

    assert state_path("btcusdt").endswith("trader_state_BTCUSDT.json")
    assert state_path("ETHUSDT") != state_path("BTCUSDT")


def test_load_env_does_not_override(tmp_path, monkeypatch):
    import run

    env_file = tmp_path / ".env"
    env_file.write_text("FOO_TEST_KEY=dosyadan\nBAR_TEST_KEY='tirnakli'\n# yorum\n")
    monkeypatch.setenv("FOO_TEST_KEY", "ortamdan")
    monkeypatch.delenv("BAR_TEST_KEY", raising=False)
    run.load_env(str(env_file))
    assert os.environ["FOO_TEST_KEY"] == "ortamdan"  # mevcut degisken ezilmez
    assert os.environ["BAR_TEST_KEY"] == "tirnakli"


def test_new_strategies_produce_valid_positions():
    from bot.backtest import run_backtest
    from bot.strategies import DonchianBreakout, EmaCross

    candles = data.synthetic(n=600, seed=8)
    for strat in (EmaCross(12, 26), DonchianBreakout(20, 10)):
        positions = strat.target_positions(candles)
        assert len(positions) == len(candles)
        assert set(positions) <= {0, 1}
        res = run_backtest(candles, strat)
        assert len(res.equity_curve) == len(candles)


def test_trailing_exit():
    from bot.risk import trailing_exit

    cfg = RiskConfig(trailing_stop_pct=3.0)
    assert trailing_exit(100.0, 96.9, cfg) is True   # tepe 100'den %3+ dusus
    assert trailing_exit(100.0, 97.5, cfg) is False
    off = RiskConfig(trailing_stop_pct=0.0)
    assert trailing_exit(100.0, 50.0, off) is False  # kapaliyken asla tetiklenmez


def test_walk_forward_segments():
    from bot.scanner import walk_forward
    from bot.strategies import SmaCross

    candles = data.synthetic(n=1000, seed=9)
    returns = walk_forward(candles, SmaCross(10, 30), segments=5)
    assert len(returns) == 5
    with pytest.raises(ValueError):
        walk_forward(candles[:100], SmaCross(10, 30), segments=5)  # dilim cok kucuk


def test_profit_factor():
    from bot.backtest import Result, Trade

    res = Result(
        strategy="x", start_equity=1, end_equity=1, total_return_pct=0,
        buy_hold_return_pct=0, max_drawdown_pct=0,
        trades=[
            Trade(0, 1, 1, 1, pnl_pct=6.0),
            Trade(0, 1, 1, 1, pnl_pct=-2.0),
            Trade(0, 1, 1, 1, pnl_pct=-1.0),
        ],
    )
    assert abs(res.profit_factor - 2.0) < 1e-9


def test_atr_positive_after_warmup():
    from bot.indicators import atr

    candles = data.synthetic(n=200, seed=10)
    values = atr(
        [c.high for c in candles], [c.low for c in candles], [c.close for c in candles], 14
    )
    assert values[13] is None  # isinma donemi
    computed = [v for v in values if v is not None]
    assert computed and all(v > 0 for v in computed)


def test_trend_filter_blocks_below_trend():
    from bot.strategies import BuyHold, TrendFilter

    candles = data.synthetic(n=400, seed=11)
    closes = [c.close for c in candles]
    from bot.indicators import sma

    trend = sma(closes, 200)
    positions = TrendFilter(BuyHold(), 200).target_positions(candles)
    for i, p in enumerate(positions):
        if trend[i] is None or closes[i] <= trend[i]:
            assert p == 0  # trend altinda alim yasak
        else:
            assert p == 1


def test_trade_csv_written(tmp_path, monkeypatch):
    from bot import trader as trader_mod
    from bot.exchange import BinanceSpot
    from bot.strategies import BuyHold
    from bot.trader import Trader, TraderConfig

    monkeypatch.setattr(trader_mod, "_BASE_DIR", str(tmp_path))
    t = Trader(BuyHold(), TraderConfig(symbol="TESTUSDT", mode="paper", start_equity=1000.0),
               BinanceSpot(testnet=False))
    t.state.update({"cash": 0.0, "qty": 1.0, "entry_price": 100.0})
    t._sell_all(110.0, "test")
    csv_path = tmp_path / "trades_TESTUSDT.csv"
    assert csv_path.exists()
    lines = csv_path.read_text().strip().splitlines()
    assert lines[0].startswith("zaman,")
    assert ",100.0,110.0,10.0000,test" in lines[1]
