"""Binance spot borsa istemcisi (stdlib-only).

Uc mod:
- paper:   emir gonderilmez, her sey simulasyon (anahtar gerekmez)
- testnet: Binance Spot Testnet'e GERCEK emir gonderir ama para SAHTEDIR
           (https://testnet.binance.vision adresinden ucretsiz anahtar al)
- live:    GERCEK PARA. Kendi Binance hesabinin API anahtari gerekir.
           Anahtari olustururken SADECE "spot trade" izni ver,
           "withdraw" (para cekme) iznini ASLA acma.

API anahtarlari ortam degiskeninden okunur, koda/dosyaya yazilmaz:
  BINANCE_API_KEY, BINANCE_API_SECRET
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .data import Candle

TESTNET_BASE = "https://testnet.binance.vision"
LIVE_BASES = ("https://api.binance.com", "https://api.binance.us")


class ExchangeError(RuntimeError):
    pass


class BinanceSpot:
    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._base: str | None = TESTNET_BASE if testnet else None

    # -- dusuk seviye ---------------------------------------------------
    def _request(self, method: str, path: str, params: dict | None = None, signed: bool = False) -> dict | list:
        params = dict(params or {})
        if signed:
            if not self.api_key or not self.api_secret:
                raise ExchangeError(
                    "API anahtari yok. BINANCE_API_KEY ve BINANCE_API_SECRET "
                    "ortam degiskenlerini ayarlayin."
                )
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            query = urllib.parse.urlencode(params)
            params["signature"] = sign(query, self.api_secret)
        query = urllib.parse.urlencode(params)
        last_err: Exception | None = None
        for base in [self._base] if self._base else list(LIVE_BASES):
            url = f"{base}{path}"
            if method == "GET" and query:
                url += f"?{query}"
                body = None
            else:
                body = query.encode() if query else None
            req = urllib.request.Request(url, data=body, method=method)
            if self.api_key:
                req.add_header("X-MBX-APIKEY", self.api_key)
            if body is not None:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read().decode())
                self._base = base  # calisan base'i hatirla
                return result
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code == 451 and base != LIVE_BASES[-1]:
                    last_err = ExchangeError(f"{base}: bolgesel engel (451)")
                    continue  # siradaki base'i dene
                raise ExchangeError(f"Binance hatasi {e.code}: {detail}") from e
            except Exception as e:  # noqa: BLE001
                last_err = e
        raise ExchangeError(f"Borsaya ulasilamadi: {last_err}")

    # -- halka acik -----------------------------------------------------
    def klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> list[Candle]:
        raw = self._request(
            "GET", "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)},
        )
        return [
            Candle(ts=int(k[0]), open=float(k[1]), high=float(k[2]),
                   low=float(k[3]), close=float(k[4]), volume=float(k[5]))
            for k in raw
        ]

    def price(self, symbol: str) -> float:
        data = self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])

    # -- imzali (hesap gerektirir) ---------------------------------------
    def balances(self) -> dict[str, float]:
        data = self._request("GET", "/api/v3/account", signed=True)
        return {
            b["asset"]: float(b["free"])
            for b in data["balances"]
            if float(b["free"]) > 0
        }

    def market_buy_quote(self, symbol: str, quote_amount: float) -> dict:
        """quote_amount (ör. 100 USDT) kadar piyasa fiyatindan alir."""
        return self._request(
            "POST", "/api/v3/order",
            {"symbol": symbol, "side": "BUY", "type": "MARKET",
             "quoteOrderQty": f"{quote_amount:.2f}"},
            signed=True,
        )

    def market_sell_qty(self, symbol: str, qty: float) -> dict:
        """qty adet baz varligi piyasa fiyatindan satar."""
        return self._request(
            "POST", "/api/v3/order",
            {"symbol": symbol, "side": "SELL", "type": "MARKET", "quantity": f"{qty:.6f}"},
            signed=True,
        )


def sign(query: str, secret: str) -> str:
    """Binance HMAC-SHA256 imzasi."""
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
