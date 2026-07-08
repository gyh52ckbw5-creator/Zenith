"""Kucuk, guvenli yerel araclar. Zenith, LLM'e gitmeden once kullanicinin
mesajinin bu araclardan birine uydugunu kontrol eder (guvenilir sekilde her
saglayicida calisan bir 'function calling' katmani olmadigi icin basit ve
ongorulebilir bir komut eslesmesi tercih edildi)."""

from __future__ import annotations

import ast
import operator
import os
import re
import sys
from datetime import datetime

_TRADING_BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trading_bot")

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Desteklenmeyen ifade")


def calculate(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    result = _safe_eval(tree.body)
    return str(result)


CALC_PATTERN = re.compile(r"^\s*(?:hesapla|calc)\s*[:=]?\s*(.+)$", re.IGNORECASE)
TIME_PATTERN = re.compile(r"^\s*(?:saat kac|tarih ne|what time|now)\s*\??\s*$", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"^\s*fiyat\s+([A-Za-z0-9=.^\-]+)\s*\??\s*$", re.IGNORECASE)
MARKET_PATTERN = re.compile(r"^\s*piyasa(?:\s+tara)?\s*[:=]?\s*([A-Za-z0-9,\s]*?)\s*$", re.IGNORECASE)


def _load_trading_bot():
    """trading_bot paketini tembel yukler (Zenith'in acilisini yavaslatmasin)."""
    if _TRADING_BOT_DIR not in sys.path:
        sys.path.insert(0, _TRADING_BOT_DIR)
    from bot import data, scanner  # noqa: PLC0415
    from bot.exchange import BinanceSpot  # noqa: PLC0415

    return data, scanner, BinanceSpot


def price_lookup(symbol: str) -> str:
    """Guncel fiyat: USDT ile bitenler Binance'ten, digerleri Yahoo'dan."""
    data, _, BinanceSpot = _load_trading_bot()
    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        price = BinanceSpot(testnet=False).price(symbol)
    else:
        candles = data.fetch_yahoo(data.yahoo_symbol(symbol), "1d", 2)
        price = candles[-1].close
    return f"{symbol} guncel fiyat: {price:,.4f}"


def market_scan(symbols_text: str, fetch=None) -> str:
    """Trading bot tarayicisiyla hizli piyasa taramasi (egitim amacli)."""
    data, scanner, BinanceSpot = _load_trading_bot()
    symbols = [s.strip().upper() for s in symbols_text.split(",") if s.strip()] or [
        "BTCUSDT", "ETHUSDT", "XAUUSD",
    ]
    if fetch is None:
        ex = BinanceSpot(testnet=False)

        def fetch(sym: str):
            if sym.endswith("USDT"):
                return ex.klines(sym, "1d", 1000)
            return data.fetch_yahoo(data.yahoo_symbol(sym), "1d", 1000)

    results = scanner.scan(symbols, fetch)
    lines = [f"Piyasa taramasi ({', '.join(symbols)}, gunluk veri):"]
    for r in results[:3]:
        lines.append("  " + r.row())
    pick = scanner.best_pick(results)
    if pick:
        lines.append(f"Elemeyi gecen aday: {pick.symbol} + {pick.strategy}")
    else:
        lines.append("Elemeyi gecen aday yok - beklemek de bir karardir.")
    lines.append("(Egitim amaclidir, yatirim tavsiyesi degildir.)")
    return "\n".join(lines)


def try_handle_locally(user_input: str) -> str | None:
    """Mesaj yerel bir arac ile cevaplanabiliyorsa cevabi dondurur, yoksa None."""
    calc_match = CALC_PATTERN.match(user_input)
    if calc_match:
        try:
            return f"Sonuc: {calculate(calc_match.group(1))}"
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
            return "Bu ifadeyi hesaplayamadim, lutfen basit bir matematik ifadesi yaz (orn: hesapla: 12*7)."

    if TIME_PATTERN.match(user_input):
        return f"Su an: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    price_match = PRICE_PATTERN.match(user_input)
    if price_match:
        try:
            return price_lookup(price_match.group(1))
        except Exception as e:  # noqa: BLE001 - ag/sembol hatasi kullaniciya soylensin
            return f"Fiyat alinamadi ({e}). Ornek: 'fiyat BTCUSDT' veya 'fiyat EURUSD'."

    market_match = MARKET_PATTERN.match(user_input)
    if market_match:
        try:
            return market_scan(market_match.group(1))
        except Exception as e:  # noqa: BLE001
            return f"Piyasa taramasi yapilamadi ({e}). Ornek: 'piyasa tara: BTCUSDT,XAUUSD'."

    return None
