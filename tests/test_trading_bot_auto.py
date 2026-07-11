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


def test_yahoo_symbol_mapping():
    assert data.yahoo_symbol("EURUSD") == "EURUSD=X"
    assert data.yahoo_symbol("usdtry") == "USDTRY=X"
    assert data.yahoo_symbol("XAUUSD") == "GC=F"
    assert data.yahoo_symbol("BTCUSDT") == "BTCUSDT"  # kripto dokunulmaz
    assert data.yahoo_symbol("GC=F") == "GC=F"


def test_parse_yahoo_skips_null_bars():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [100, 200, 300],
                    "indicators": {
                        "quote": [
                            {
                                "open": [1.0, None, 1.2],
                                "high": [1.1, 1.1, 1.3],
                                "low": [0.9, 0.9, 1.1],
                                "close": [1.05, 1.0, 1.25],
                                "volume": [10, 20, None],
                            }
                        ]
                    },
                }
            ]
        }
    }
    candles = data.parse_yahoo(payload)
    assert len(candles) == 2  # null'lu bar atlandi
    assert candles[0].ts == 100_000 and candles[1].volume == 0


def test_ai_comment_silent_without_key(monkeypatch):
    from bot.ai_analyst import ai_available, ai_comment

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert ai_available() is False
    assert ai_comment("ozet") is None


def test_format_qty_no_scientific_notation():
    from bot.exchange import format_qty

    assert format_qty(0.00001) == "0.00001"   # 1e-05 degil
    assert format_qty(1.230000) == "1.23"
    assert format_qty(5.0) == "5"


def test_round_qty_floors_to_step():
    from bot.exchange import BinanceSpot

    ex = BinanceSpot(testnet=False)
    ex._filters["XUSDT"] = {"LOT_SIZE": {"stepSize": "0.001", "minQty": "0.01"}}
    assert abs(ex.round_qty("XUSDT", 1.23456) - 1.234) < 1e-12  # asagi yuvarlar
    assert ex.round_qty("XUSDT", 0.005) == 0.0                  # minQty alti = 0


def test_render_html_contains_svg_and_stats():
    from bot.backtest import run_backtest
    from bot.report_html import render_html
    from bot.strategies import SmaCross

    candles = data.synthetic(n=400, seed=12)
    result = run_backtest(candles, SmaCross(10, 30))
    html = render_html(result, candles, "Test Raporu")
    assert "<svg" in html and "polyline" in html
    assert "Toplam getiri" in html and "Test Raporu" in html
    assert "Uyari" in html  # egitim uyarisi her raporda olmali


def test_bollinger_and_macd_strategies():
    from bot.backtest import run_backtest
    from bot.strategies import BollingerReversion, MacdCross

    candles = data.synthetic(n=600, seed=13)
    for strat in (BollingerReversion(20, 2.0), MacdCross()):
        positions = strat.target_positions(candles)
        assert len(positions) == len(candles)
        assert set(positions) <= {0, 1}
        res = run_backtest(candles, strat)
        assert len(res.equity_curve) == len(candles)


def test_bollinger_bands_order():
    from bot.indicators import bollinger

    closes = [c.close for c in data.synthetic(n=100, seed=14)]
    mid, upper, lower = bollinger(closes, 20, 2.0)
    for i in range(len(closes)):
        if mid[i] is not None:
            assert lower[i] < mid[i] < upper[i]


def test_cooldown_blocks_reentry(tmp_path, monkeypatch):
    import time as _time

    from bot import trader as trader_mod
    from bot.exchange import BinanceSpot
    from bot.strategies import BuyHold
    from bot.trader import Trader, TraderConfig

    monkeypatch.setattr(trader_mod, "_BASE_DIR", str(tmp_path))
    cfg = TraderConfig(symbol="TESTUSDT", mode="paper", start_equity=1000.0,
                       risk=RiskConfig(cooldown_bars=3, stoploss_guard=2))
    t = Trader(BuyHold(), cfg, BinanceSpot(testnet=False))
    t.state.update({"cash": 0.0, "qty": 1.0, "entry_price": 100.0})
    t._sell_all(97.0, "stop_loss")
    t._after_stop("2026-01-01")
    assert t.state["cooldown_until"] > _time.time()  # giris kilitli
    assert t.state["stops_today"] == 1
    # ikinci stop guard limitine carpar, gun kapanir
    t.state.update({"cash": 0.0, "qty": 1.0, "entry_price": 100.0})
    t._sell_all(97.0, "stop_loss")
    t._after_stop("2026-01-01")
    assert t.state["halted_day"] == "2026-01-01"


def _mk(ts, o, h, l, c):
    return data.Candle(ts=ts, open=o, high=h, low=l, close=c, volume=1)


def test_backtest_stop_loss_triggers_intrabar():
    from bot.backtest import run_backtest
    from bot.strategies import BuyHold

    candles = [
        _mk(1, 100, 101, 99, 100),   # sinyal mumu
        _mk(2, 100, 102, 100, 101),  # giris @ 100 (acilis)
        _mk(3, 101, 103, 94, 95),    # dip 94 -> %2 stop (98) mum icinde vurulur
        _mk(4, 95, 96, 94, 95),
    ]
    res = run_backtest(candles, BuyHold(), commission_pct=0, slippage_pct=0,
                       stop_loss_pct=2.0, cooldown_bars=10)
    stops = [t for t in res.trades if t.reason == "stop_loss"]
    assert len(stops) == 1
    assert abs(stops[0].exit_price - 98.0) < 1e-9   # tam stop fiyatindan cikis
    assert abs(stops[0].pnl_pct - (-2.0)) < 1e-9
    # cooldown sayesinde tekrar giris yok (BuyHold hep 1 istemesine ragmen)
    assert len(res.trades) == 1


def test_backtest_take_profit_triggers_intrabar():
    from bot.backtest import run_backtest
    from bot.strategies import BuyHold

    candles = [
        _mk(1, 100, 101, 99, 100),
        _mk(2, 100, 100, 99, 100),   # giris @ 100
        _mk(3, 100, 106, 100, 105),  # tepe 106 -> %4 hedef (104) vurulur
        _mk(4, 105, 106, 104, 105),
    ]
    res = run_backtest(candles, BuyHold(), commission_pct=0, slippage_pct=0,
                       take_profit_pct=4.0)
    tps = [t for t in res.trades if t.reason == "take_profit"]
    assert len(tps) == 1 and abs(tps[0].exit_price - 104.0) < 1e-9


def test_backtest_no_risk_flags_matches_old_behavior():
    from bot.backtest import run_backtest
    from bot.strategies import SmaCross

    candles = data.synthetic(n=500, seed=15)
    plain = run_backtest(candles, SmaCross(10, 30))
    with_off_flags = run_backtest(candles, SmaCross(10, 30),
                                  stop_loss_pct=0, take_profit_pct=0,
                                  trailing_stop_pct=0, cooldown_bars=0)
    assert plain.end_equity == with_off_flags.end_equity
    assert all(t.reason in ("sinyal", "acik") for t in plain.trades)


def test_equity_history_recorded_and_capped(tmp_path, monkeypatch):
    from bot import trader as trader_mod
    from bot.exchange import BinanceSpot
    from bot.strategies import BuyHold
    from bot.trader import Trader, TraderConfig

    monkeypatch.setattr(trader_mod, "_BASE_DIR", str(tmp_path))
    t = Trader(BuyHold(), TraderConfig(symbol="TESTUSDT", mode="paper", start_equity=1000.0),
               BinanceSpot(testnet=False))
    for i in range(5010):
        t._record_equity(1000.0 + i)
    hist = t.state["equity_history"]
    assert len(hist) == 5000            # tavan calisiyor
    assert hist[-1][1] == 1000.0 + 5009  # en yeni kayit korunuyor


def test_render_live_html():
    from bot.report_html import render_live_html

    histories = {
        "BTCUSDT": [[1, 1000.0], [2, 1010.0], [3, 990.0]],
        "ETHUSDT": [[1, 500.0], [2, 505.0], [3, 520.0]],
        "BOS": [[1, 100.0]],  # tek nokta cizilmez, sessizce atlanir
    }
    html = render_live_html(histories, "Portfoy")
    assert "<svg" in html and html.count("polyline") == 2
    assert "BTCUSDT" in html and "+4.00%" in html  # ETH degisimi


def test_sample_strategy_always_valid():
    import random

    from bot.optimize import sample_strategy

    rng = random.Random(0)
    for kind in ("sma", "ema", "rsi", "donchian", "bollinger", "macd"):
        for _ in range(50):
            strat = sample_strategy(kind, rng)  # gecersiz parametre ValueError firlatirdi
            assert strat.name


def test_optimize_sorted_by_median():
    from bot.optimize import optimize

    candles = data.synthetic(n=1000, seed=16)
    results = optimize(candles, "sma", trials=8, segments=4, seed=1)
    assert results
    medians = [r.median_pct for r in results]
    assert medians == sorted(medians, reverse=True)
    assert all(len(r.segments) == 4 for r in results)


def test_yahoo_4h_falls_back_to_1h():
    # 4h Yahoo'da yok; ValueError yerine 1h'e dusmeli (URL kurulana kadar
    # hata firlatmamasi yeterli - ag cagrisina gelmeden interval dogrulanir)
    import urllib.request

    captured = {}

    class _Fake:
        def __enter__(self):
            captured["ok"] = True
            raise RuntimeError("ag-yok")

        def __exit__(self, *a):
            return False

    orig = urllib.request.urlopen
    try:
        def fake_urlopen(req, timeout=0):
            captured["url"] = req.full_url
            raise RuntimeError("ag-yok")

        urllib.request.urlopen = fake_urlopen
        with pytest.raises(RuntimeError, match="ag-yok"):
            data.fetch_yahoo("EURUSD=X", "4h", 10)
        assert "interval=1h" in captured["url"]
    finally:
        urllib.request.urlopen = orig


def test_symbol_presets_expand():
    import run

    assert run.parse_symbols("FOREX") == ["EURUSD", "GBPUSD", "USDJPY", "USDTRY", "XAUUSD"]
    assert run.parse_symbols("kripto") == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert run.parse_symbols("BTCUSDT, eurusd") == ["BTCUSDT", "EURUSD"]  # normal liste bozulmaz
    assert "XAUUSD" in run.parse_symbols("FOREX,DOGEUSDT")  # kisayol + ek sembol karisabilir


def test_telegram_commander_handle(tmp_path, monkeypatch):
    import json as _json

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    from bot import telegram_bot

    monkeypatch.setattr(telegram_bot, "_BASE_DIR", str(tmp_path))
    (tmp_path / "trader_state_BTCUSDT.json").write_text(
        _json.dumps({"cash": 0.0, "qty": 1.0, "equity_history": [[1, 1000.0], [2, 1050.0]]})
    )
    (tmp_path / "trades_BTCUSDT.csv").write_text(
        "zaman,mod,sembol,giris,cikis,kz_yuzde,neden\n2026-01-01,paper,BTCUSDT,100,110,10,test\n"
    )
    c = telegram_bot.TelegramCommander()
    monkeypatch.setattr(c, "_fiyat", lambda s: f"{s}: 42")  # ag cagrisi yok

    assert "1,050.00" in c.handle("/durum") and "pozisyonda" in c.handle("/durum")
    assert c.handle("/fiyat btcusdt".upper()) == "BTCUSDT: 42"
    assert "BTCUSDT,100,110,10,test" in c.handle("/rapor")
    assert c.handle("/yardim") == telegram_bot.HELP_TEXT
    assert c.handle("saçma bir mesaj") == telegram_bot.HELP_TEXT  # bilinmeyen -> yardim
    assert c.handle("/durum@Z2nith_bot").startswith("Sanal portfoy")  # @bot eki ayiklanir


def test_symbol_currencies_mapping():
    from bot.news import symbol_currencies

    assert symbol_currencies("BTCUSDT") == {"USD"}
    assert symbol_currencies("EURUSD") == {"EUR", "USD"}
    assert symbol_currencies("XAUUSD") == {"USD"}
    assert symbol_currencies("USDTRY") == {"USD", "TRY"}
    assert "USD" in symbol_currencies("BILINMEYEN")  # varsayilan USD


def test_news_blackout_window():
    from bot.news import news_blackout

    now = 1_700_000_000.0
    events = [{"ts": now + 20 * 60, "country": "USD", "title": "FOMC"}]
    blocked, event = news_blackout("BTCUSDT", now=now, window_min=30, events=events)
    assert blocked and "FOMC" in event
    # pencere disi (45 dk sonra) -> serbest
    assert news_blackout("BTCUSDT", now=now - 26 * 60, window_min=30, events=events)[0] is False
    # baska para birimi -> serbest
    assert news_blackout("EURUSD", now=now, window_min=30,
                         events=[{"ts": now, "country": "JPY", "title": "BoJ"}])[0] is False
    # bos takvim -> serbest (fail-open)
    assert news_blackout("BTCUSDT", now=now, events=[])[0] is False


def test_adx_bounds_and_warmup():
    from bot.indicators import adx

    candles = data.synthetic(n=300, seed=17)
    values = adx([c.high for c in candles], [c.low for c in candles],
                 [c.close for c in candles], 14)
    assert values[:28] == [None] * 28  # 2*period isinma
    computed = [v for v in values if v is not None]
    assert computed and all(0 <= v <= 100 for v in computed)


def test_full_report_sections():
    from bot.analyst import full_report

    candles = data.synthetic(n=800, seed=18)
    report = full_report("TESTUSDT", candles)
    for needle in ("Rejim", "Trend", "Momentum", "Oynaklik", "Seviyeler",
                   "Getiri", "Strateji", "GENEL", "Egitim amaclidir"):
        assert needle in report, needle
    # kisa veri durustce reddedilir
    assert "en az 260 mum" in full_report("X", candles[:100])
