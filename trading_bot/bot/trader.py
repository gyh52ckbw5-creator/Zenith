"""Otomatik islem dongusu: analiz -> karar -> risk kontrolu -> emir.

Akis (her mum periyodunda bir tur):
 1. Guncel mumlar cekilir, strateji hedef pozisyonu uretir.
 2. Acik pozisyon varsa stop-loss / take-profit kontrol edilir.
 3. Gunluk zarar freni (kill switch) asildiysa her sey satilir, o gun durulur.
 4. Karara gore emir: paper modda simulasyon, testnet/live modda gercek emir.

Durum `trader_state.json` dosyasinda tutulur; bot yeniden baslatilinca
kaldigi yerden devam eder.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from .exchange import BinanceSpot, ExchangeError
from .notify import send_telegram
from .risk import RiskConfig, daily_kill_switch, exit_reason, position_size_quote
from .strategies import Strategy

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INTERVAL_SEC = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}


def state_path(symbol: str) -> str:
    return os.path.join(_BASE_DIR, f"trader_state_{symbol.upper()}.json")


@dataclass
class TraderConfig:
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    mode: str = "paper"  # paper | testnet | live
    start_equity: float = 1000.0  # sadece paper modda kullanilir
    risk: RiskConfig | None = None


class Trader:
    def __init__(self, strategy: Strategy, cfg: TraderConfig, exchange: BinanceSpot):
        self.strategy = strategy
        self.cfg = cfg
        self.risk = cfg.risk or RiskConfig()
        self.risk.validate()
        self.ex = exchange
        self.state_file = state_path(cfg.symbol)
        self.state = self._load_state()

    # -- durum -----------------------------------------------------------
    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file, encoding="utf-8") as f:
                return json.load(f)
        return {
            "cash": self.cfg.start_equity,  # paper mod sanal bakiyesi
            "qty": 0.0,
            "entry_price": 0.0,
            "day": "",
            "day_start_equity": 0.0,
            "halted_day": "",
            "log": [],
        }

    def _save_state(self) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def _log(self, msg: str, equity: float, notify: bool = False) -> None:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] [{self.cfg.mode}] [{self.cfg.symbol}] {msg} | toplam: {equity:.2f}"
        print(line)
        self.state["log"] = (self.state["log"] + [line])[-500:]
        if notify:  # sadece onemli olaylar telefona gider, "bekle" mesajlari gitmez
            send_telegram(line)

    # -- bakiye ------------------------------------------------------------
    def equity(self, price: float) -> float:
        if self.cfg.mode == "paper":
            return self.state["cash"] + self.state["qty"] * price
        balances = self.ex.balances()
        base = self.cfg.symbol.replace("USDT", "")
        return balances.get("USDT", 0.0) + balances.get(base, 0.0) * price

    # -- emirler -----------------------------------------------------------
    def _buy(self, price: float, quote_amount: float) -> None:
        if quote_amount < 10:  # Binance minimum emir buyuklugu civari
            self._log(f"pozisyon cok kucuk ({quote_amount:.2f}), islem yok", self.equity(price))
            return
        if self.cfg.mode == "paper":
            qty = quote_amount / price
            self.state["cash"] -= quote_amount
            self.state["qty"] += qty
        else:
            order = self.ex.market_buy_quote(self.cfg.symbol, quote_amount)
            qty = float(order.get("executedQty", 0))
            self.state["qty"] += qty
        self.state["entry_price"] = price
        self._log(f"ALIM {quote_amount:.2f} karsiligi @ {price}", self.equity(price), notify=True)

    def _sell_all(self, price: float, reason: str) -> None:
        qty = self.state["qty"]
        if qty <= 0:
            return
        if self.cfg.mode == "paper":
            self.state["cash"] += qty * price
        else:
            self.ex.market_sell_qty(self.cfg.symbol, qty)
        self.state["qty"] = 0.0
        pnl = 100.0 * (price / self.state["entry_price"] - 1) if self.state["entry_price"] else 0.0
        self.state["entry_price"] = 0.0
        self._log(f"SATIS ({reason}) @ {price}, islem k/z: {pnl:+.2f}%", self.equity(price), notify=True)

    # -- tek tur -----------------------------------------------------------
    def step(self) -> None:
        candles = self.ex.klines(self.cfg.symbol, self.cfg.interval, 250)
        price = candles[-1].close
        equity = self.equity(price)
        today = time.strftime("%Y-%m-%d")

        if self.state["day"] != today:
            self.state["day"] = today
            self.state["day_start_equity"] = equity

        # gunluk zarar freni
        if self.state["halted_day"] == today:
            self._log("gunluk zarar limiti asildi, bugun islem yok", equity)
            return
        if daily_kill_switch(self.state["day_start_equity"], equity, self.risk):
            self._sell_all(price, "gunluk zarar freni")
            self.state["halted_day"] = today
            self._log(
                f"KILL SWITCH: gunluk zarar > %{self.risk.max_daily_loss_pct}, duruldu",
                self.equity(price),
                notify=True,
            )
            return

        in_position = self.state["qty"] > 0

        # stop-loss / take-profit sinyalden once kontrol edilir
        if in_position:
            reason = exit_reason(self.state["entry_price"], price, self.risk)
            if reason:
                self._sell_all(price, reason)
                return

        target = self.strategy.target_positions(candles)[-1]
        if target == 1 and not in_position:
            self._buy(price, position_size_quote(equity, self.risk))
        elif target == 0 and in_position:
            self._sell_all(price, "strateji sinyali")
        else:
            self._log(
                f"bekle (fiyat {price}, {'pozisyonda' if in_position else 'nakitte'})",
                equity,
            )

    def run_forever(self) -> None:
        run_many([self])


def run_many(traders: list["Trader"]) -> None:
    """Birden fazla sembolu ayni dongude izler. Ctrl+C ile durdurulur."""
    if not traders:
        return
    sleep_s = min(INTERVAL_SEC.get(t.cfg.interval, 3600) for t in traders)
    first = traders[0]
    print(
        f"Bot basladi: {', '.join(t.cfg.symbol for t in traders)} "
        f"({first.cfg.interval}), strateji {first.strategy.name}, mod: {first.cfg.mode.upper()}\n"
        f"Risk: islem basina %{first.risk.risk_pct_per_trade}, stop %{first.risk.stop_loss_pct}, "
        f"hedef %{first.risk.take_profit_pct}, gunluk fren %{first.risk.max_daily_loss_pct}\n"
    )
    while True:
        for t in traders:
            try:
                t.step()
                t._save_state()
            except ExchangeError as e:
                print(f"[{t.cfg.symbol}] borsa hatasi: {e} - sonraki turda tekrar")
            except KeyboardInterrupt:
                for tr in traders:
                    tr._save_state()
                print("\nDurduruldu, durumlar kaydedildi.")
                return
        try:
            time.sleep(sleep_s)
        except KeyboardInterrupt:
            for tr in traders:
                tr._save_state()
            print("\nDurduruldu, durumlar kaydedildi.")
            return
