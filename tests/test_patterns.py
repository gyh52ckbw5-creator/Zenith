"""Mum formasyonu testleri - elle kurgulanmis mumlarla birebir dogrulama."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot.data import Candle  # noqa: E402
from bot.patterns import (  # noqa: E402
    engulfing,
    hammer_hanging,
    pattern_report,
    piercing_darkcloud,
    scan_patterns,
    soldiers_crows,
    star_doji,
)


def _c(o, h, l, c, ts=0):
    return Candle(ts=ts, open=o, high=h, low=l, close=c, volume=1)


def test_bullish_engulfing():
    candles = [_c(105, 106, 99, 100), _c(99.5, 107, 99, 106)]  # ayi + yutan boga
    assert engulfing(candles)[-1] == 1


def test_bearish_engulfing():
    candles = [_c(100, 106, 99, 105), _c(105.5, 106, 98, 99)]
    assert engulfing(candles)[-1] == -1


def test_hammer_after_downtrend():
    candles = [
        _c(110, 111, 107, 108), _c(108, 109, 105, 106), _c(106, 107, 103, 104),
        _c(104, 104.6, 100, 104.3),  # dusus dibinde cekic: uzun alt fitil
    ]
    assert hammer_hanging(candles)[-1] == 1


def test_morning_star():
    candles = [
        _c(110, 111, 104, 105),      # buyuk ayi
        _c(104.8, 105.2, 104.5, 104.9),  # doji
        _c(105, 109, 104.9, 108.5),  # boga, ilk govdenin yarisini gecti
    ]
    assert star_doji(candles)[-1] == 1


def test_piercing_line():
    candles = [_c(110, 111, 104, 105), _c(104.5, 109, 104, 108)]  # yari govdeyi deler
    assert piercing_darkcloud(candles)[-1] == 1


def test_three_white_soldiers():
    candles = [_c(100, 103, 99.8, 102.8), _c(102, 105, 101.8, 104.8), _c(104, 107, 103.8, 106.8)]
    assert soldiers_crows(candles)[-1] == 1


def test_scan_and_report():
    candles = [_c(105, 106, 99, 100), _c(99.5, 107, 99, 106)]
    found = scan_patterns(candles)
    assert any(name == "yutan" and d == "yukari" for name, d, _ in found)
    text = pattern_report(candles, "TEST")
    assert "yutan" in text and "teyit" in text


def test_agent_has_formasyon_tool():
    from zenith.agent import TOOLS
    assert "formasyon" in TOOLS
