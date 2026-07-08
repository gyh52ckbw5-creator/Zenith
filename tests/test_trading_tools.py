"""Zenith ajaninin trading araclari testleri."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot import data as bot_data  # noqa: E402

from zenith import trading_tools  # noqa: E402


def test_parse_free_text():
    assert trading_tools._parse("XAUUSD sma 1d") == ("XAUUSD", "sma", "1d")
    assert trading_tools._parse("donchian eurusd") == ("EURUSD", "donchian", "1d")
    assert trading_tools._parse("") == ("BTCUSDT", "sma", "1d")  # varsayilanlar
    assert trading_tools._parse("4h macd ethusdt") == ("ETHUSDT", "macd", "4h")


def test_backtest_and_walkforward_text(monkeypatch):
    monkeypatch.setattr(
        trading_tools, "_candles",
        lambda symbol, interval, bars=1000: bot_data.synthetic(n=800, seed=3),
    )
    out = trading_tools.backtest_text("XAUUSD sma 1d")
    assert "backtest" in out and "Toplam getiri" in out and "Egitim amaclidir" in out
    wf = trading_tools.walkforward_text("XAUUSD sma 1d")
    assert "walk-forward" in wf and "/5" in wf


def test_portfolio_text(tmp_path, monkeypatch):
    st = {"cash": 0.0, "qty": 0.5, "entry_price": 100.0,
          "equity_history": [[1, 1000.0], [2, 1100.0]], "log": ["[t] ALIM x"]}
    (tmp_path / "trader_state_BTCUSDT.json").write_text(json.dumps(st))
    monkeypatch.setattr(trading_tools, "_TB", str(tmp_path))
    out = trading_tools.portfolio_text()
    assert "BTCUSDT" in out and "+10.00%" in out and "Toplam: 1,100.00" in out


def test_agent_has_trading_tools():
    from zenith.agent import TOOLS

    for name in ("fiyat", "piyasa", "backtest", "walkforward", "optimize", "portfoy"):
        assert name in TOOLS, name
