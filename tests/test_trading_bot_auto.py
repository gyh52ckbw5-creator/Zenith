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

    results = scan(["AAA", "BBB"], fetch)
    assert len(results) == 2 * 7  # 2 sembol x 7 kombinasyon
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
