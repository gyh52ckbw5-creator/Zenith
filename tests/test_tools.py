from zenith.tools import try_handle_locally


def test_calculator_handles_basic_expression():
    result = try_handle_locally("hesapla: 12*7")
    assert result == "Sonuc: 84"


def test_calculator_handles_calc_alias():
    result = try_handle_locally("calc: (2+3)*4")
    assert result == "Sonuc: 20"


def test_calculator_rejects_unsafe_expression():
    result = try_handle_locally("hesapla: __import__('os').system('echo hi')")
    assert result.startswith("Bu ifadeyi hesaplayamadim")


def test_non_tool_message_returns_none():
    assert try_handle_locally("bugün nasılsın?") is None


def test_time_query():
    result = try_handle_locally("saat kac")
    assert result.startswith("Su an:")


def test_market_scan_with_injected_fetch():
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))
    from bot import data as bot_data

    from zenith.tools import market_scan

    def fake_fetch(symbol: str):
        return bot_data.synthetic(n=600, seed=abs(hash(symbol)) % 50)

    result = market_scan("AAA,BBB", fetch=fake_fetch)
    assert result.startswith("Piyasa taramasi")
    assert "yatirim tavsiyesi degildir" in result


def test_price_pattern_does_not_swallow_normal_chat():
    from zenith.tools import MARKET_PATTERN, PRICE_PATTERN

    assert PRICE_PATTERN.match("fiyat BTCUSDT")
    assert PRICE_PATTERN.match("fiyat EURUSD ?")
    assert not PRICE_PATTERN.match("fiyatlar cok yukseldi bugun")
    assert MARKET_PATTERN.match("piyasa tara: BTCUSDT,XAUUSD")
    assert MARKET_PATTERN.match("piyasa")
    assert not MARKET_PATTERN.match("piyasa hakkinda ne dusunuyorsun dostum?")
