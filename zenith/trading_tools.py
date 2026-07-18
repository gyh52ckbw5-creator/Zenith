"""Zenith ajani icin trading araclari - trading_bot koprusu.

Ajan modunda model bu araclari dogal konusma icinde kendisi cagirir:
"altinda sma stratejisi nasil gitmis?" -> ARAC: backtest | XAUUSD sma 1d

Arguman ayristirma esnektir: bosluk/virgulle ayrilmis kelimelerden strateji
adi (sma, ema, rsi, donchian, bollinger, macd), periyot (1m..1d) ve sembol
kendiliginden secilir; eksikler makul varsayilanla doldurulur.
"""

from __future__ import annotations

import glob
import json
import os
import sys

_TB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trading_bot")

_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}

DISCLAIMER = "(Egitim amaclidir; gecmis performans gelecegi garanti etmez.)"


def _bot():
    """trading_bot paketini tembel yukler."""
    if _TB not in sys.path:
        sys.path.insert(0, _TB)
    from bot import backtest, data, optimize, scanner  # noqa: PLC0415
    from bot.exchange import BinanceSpot  # noqa: PLC0415
    from bot.strategies import STRATEGIES  # noqa: PLC0415

    return data, scanner, backtest, optimize, BinanceSpot, STRATEGIES


def _parse(arg: str) -> tuple[str, str, str]:
    """Serbest metinden (sembol, strateji, periyot) cikarir."""
    _, _, _, _, _, STRATEGIES = _bot()
    symbol, strategy, interval = "BTCUSDT", "sma", "1d"
    for tok in arg.replace(",", " ").split():
        t = tok.strip().lower()
        if not t:
            continue
        if t in STRATEGIES and t != "hold":
            strategy = t
        elif t in _INTERVALS:
            interval = t
        else:
            symbol = tok.strip().upper()
    return symbol, strategy, interval


def _candles(symbol: str, interval: str, bars: int = 1000):
    data, _, _, _, BinanceSpot, _ = _bot()
    if symbol.endswith("USDT"):
        return BinanceSpot(testnet=False).klines(symbol, interval, bars)
    return data.fetch_yahoo(data.yahoo_symbol(symbol), interval, bars)


def backtest_text(arg: str) -> str:
    """Tek strateji/sembol backtest ozeti."""
    symbol, strat_name, interval = _parse(arg)
    _, _, backtest, _, _, STRATEGIES = _bot()
    candles = _candles(symbol, interval)
    res = backtest.run_backtest(candles, STRATEGIES[strat_name]())
    return f"{symbol} {interval} backtest ({res.strategy}):\n{res.summary()}\n{DISCLAIMER}"


def walkforward_text(arg: str) -> str:
    """Walk-forward dogrulamasi: strateji ardisik dilimlerin kacinda ayakta?"""
    symbol, strat_name, interval = _parse(arg)
    _, scanner, _, _, _, STRATEGIES = _bot()
    candles = _candles(symbol, interval)
    returns = scanner.walk_forward(candles, STRATEGIES[strat_name](), segments=5)
    positive = sum(1 for r in returns if r >= 0)
    segs = ", ".join(f"{r:+.1f}%" for r in returns)
    verdict = (
        "cogu dilimde ayakta - incelemeye deger"
        if positive >= 3
        else "dilimlerin cogunda zararda - tek bolmede iyi gorunduyse sansti"
    )
    return (
        f"{symbol} {interval} walk-forward ({STRATEGIES[strat_name]().name}): "
        f"dilimler [{segs}], artida {positive}/5. Sonuc: {verdict}. {DISCLAIMER}"
    )


def optimize_text(arg: str) -> str:
    """Parametre optimizasyonu (walk-forward puanli), ilk 5 sonuc."""
    symbol, strat_name, interval = _parse(arg)
    _, _, _, optimize, _, _ = _bot()
    candles = _candles(symbol, interval)
    results = optimize.optimize(candles, strat_name, trials=20, segments=5)
    rows = "\n".join("  " + r.row() for r in results[:5])
    return (
        f"{symbol} {interval} icin {strat_name} optimizasyonu (ilk 5, "
        f"puan=walk-forward medyani):\n{rows}\n"
        f"Not: secim gecmise gore yapildi; canli oncesi taze veride dogrula. {DISCLAIMER}"
    )


def deep_report_text(arg: str) -> str:
    """Tek sembol cok faktorlu derin analiz (rejim, trend, momentum, seviyeler)."""
    symbol, _, interval = _parse(arg)
    if _TB not in sys.path:
        sys.path.insert(0, _TB)
    from bot.analyst import full_report  # noqa: PLC0415

    return full_report(symbol, _candles(symbol, interval))


def montecarlo_text(arg: str) -> str:
    """Backtest + Monte Carlo: sonuc ne kadar sansa bagliydi?"""
    symbol, strat_name, interval = _parse(arg)
    _, _, backtest, _, _, STRATEGIES = _bot()
    if _TB not in sys.path:
        sys.path.insert(0, _TB)
    from bot.montecarlo import monte_carlo  # noqa: PLC0415

    candles = _candles(symbol, interval)
    res = backtest.run_backtest(candles, STRATEGIES[strat_name](),
                                stop_loss_pct=3.0, take_profit_pct=9.0, cooldown_bars=5)
    mc = monte_carlo([t.pnl_pct for t in res.trades], trials=2000)
    head = f"{symbol} {interval} ({res.strategy}): gecmis getiri {res.total_return_pct:+.1f}%\n"
    if mc is None:
        return head + f"Monte Carlo icin en az 10 islem gerekir ({res.n_trades} var). {DISCLAIMER}"
    return head + mc.summary() + f"\n{DISCLAIMER}"


def patterns_text(arg: str) -> str:
    """Mum formasyonu taramasi: yutan, harami, cekic, yildiz, delen, askerler."""
    symbol, _, interval = _parse(arg)
    if _TB not in sys.path:
        sys.path.insert(0, _TB)
    from bot.patterns import pattern_report  # noqa: PLC0415

    return pattern_report(_candles(symbol, interval, 100), symbol) + f"\n{DISCLAIMER}"


def stats_text(arg: str = "") -> str:
    """Gercek islem karnesi: kapanmis islemlerden kazanma orani, beklenti, kar faktoru."""
    if _TB not in sys.path:
        sys.path.insert(0, _TB)
    from bot import stats  # noqa: PLC0415

    return stats.summary_text(_TB)


def portfolio_text(arg: str = "") -> str:
    """Calisan botun sanal portfoy durumu (trader_state_*.json)."""
    files = sorted(glob.glob(os.path.join(_TB, "trader_state_*.json")))
    if not files:
        return "Henuz calisan bot verisi yok. Bot 'trade' komutuyla baslatilinca burada gorunur."
    lines = []
    total = 0.0
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        fallback = os.path.basename(path).replace("trader_state_", "").replace(".json", "")
        symbol = st.get("symbol", fallback)
        mode = st.get("mode", "paper")
        label = f"{symbol}[{mode}]"
        hist = st.get("equity_history", [])
        equity = hist[-1][1] if hist else st.get("cash", 0.0)
        total += equity
        pos = "pozisyonda" if st.get("qty", 0) > 0 else "nakitte"
        start = hist[0][1] if hist else equity
        change = 100.0 * (equity / start - 1) if start else 0.0
        lines.append(f"  {label}: {equity:,.2f} ({pos}, degisim {change:+.2f}%)")
    last_log = ""
    try:
        with open(files[-1], encoding="utf-8") as f:
            logs = json.load(f).get("log", [])
        if logs:
            last_log = f"\nSon olay: {logs[-1]}"
    except (OSError, json.JSONDecodeError):
        pass
    return "Sanal portfoy:\n" + "\n".join(lines) + f"\nToplam: {total:,.2f}{last_log}\n{DISCLAIMER}"
