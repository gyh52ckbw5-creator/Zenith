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

from .data import Candle
from .exchange import BinanceSpot, ExchangeError
from .indicators import atr
from .news import news_blackout
from .notify import send_telegram
from .risk import RiskConfig, daily_kill_switch, exit_reason, position_size_quote, trailing_exit
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
    news_filter: bool = True  # buyuk haber saatlerinde yeni giris yapma


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
    def _buy(self, price: float, quote_amount: float, closed: list[Candle]) -> None:
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
        self.state["peak_price"] = price
        self.state["stop_price"] = 0.0
        if self.risk.atr_stop_mult > 0:
            a = atr([c.high for c in closed], [c.low for c in closed], [c.close for c in closed])
            if a[-1] is not None:
                self.state["stop_price"] = price - self.risk.atr_stop_mult * a[-1]
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
        entry = self.state["entry_price"]
        pnl = 100.0 * (price / entry - 1) if entry else 0.0
        self.state["entry_price"] = 0.0
        self.state["peak_price"] = 0.0
        self.state["stop_price"] = 0.0
        self._append_trade_csv(entry, price, pnl, reason)
        self._log(f"SATIS ({reason}) @ {price}, islem k/z: {pnl:+.2f}%", self.equity(price), notify=True)

    def _append_trade_csv(self, entry: float, exit_: float, pnl: float, reason: str) -> None:
        """Kapanan her islemi CSV'ye ekler: Excel/Sheets'te analiz icin."""
        path = os.path.join(_BASE_DIR, f"trades_{self.cfg.symbol}.csv")
        new_file = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if new_file:
                f.write("zaman,mod,sembol,giris,cikis,kz_yuzde,neden\n")
            f.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')},{self.cfg.mode},{self.cfg.symbol},"
                f"{entry},{exit_},{pnl:.4f},{reason}\n"
            )

    # -- tek tur -----------------------------------------------------------
    def step(self) -> None:
        # 400 mum: trend filtresi (200) gibi uzun isinmali stratejilere yeterli pay
        candles = self.ex.klines(self.cfg.symbol, self.cfg.interval, 400)
        # Son mum hala olusuyor: sinyal SADECE kapanmis mumlardan uretilir,
        # yoksa mum ici salinimlar ac-kapa yaptirir (backtestteki look-ahead
        # yasaginin canli karsiligi). Guncel fiyat ise emir/stop icin kullanilir.
        closed = candles[:-1]
        price = candles[-1].close
        equity = self.equity(price)
        self._record_equity(equity)
        today = time.strftime("%Y-%m-%d")

        if self.state["day"] != today:
            self.state["day"] = today
            self.state["day_start_equity"] = equity
            self.state["stops_today"] = 0

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

        # stop-loss / take-profit / iz suren stop sinyalden once kontrol edilir
        if in_position:
            peak = max(self.state.get("peak_price", 0.0), self.state["entry_price"], price)
            self.state["peak_price"] = peak
            stop_price = self.state.get("stop_price", 0.0)
            if stop_price > 0:  # ATR stop aciksa sabit yuzdeli stop yerine gecer
                reason = "atr_stop" if price <= stop_price else None
                if not reason and price >= self.state["entry_price"] * (1 + self.risk.take_profit_pct / 100):
                    reason = "take_profit"
            else:
                reason = exit_reason(self.state["entry_price"], price, self.risk)
            if not reason and trailing_exit(peak, price, self.risk):
                reason = "trailing_stop"
            if reason:
                self._sell_all(price, reason)
                if "stop" in reason:
                    self._after_stop(today)
                return

        target = self.strategy.target_positions(closed)[-1]
        if target == 1 and not in_position:
            if time.time() < self.state.get("cooldown_until", 0):
                self._log("cooldown: stop sonrasi bekleme suresi, giris yok", equity)
                return
            if self.cfg.news_filter:
                blocked, event = news_blackout(self.cfg.symbol)
                if blocked:
                    self._log(f"haber karantinasi ({event}), giris yok", equity)
                    return
            self._buy(price, position_size_quote(equity, self.risk), closed)
        elif target == 0 and in_position:
            self._sell_all(price, "strateji sinyali")
        else:
            self._log(
                f"bekle (fiyat {price}, {'pozisyonda' if in_position else 'nakitte'})",
                equity,
            )

    def _record_equity(self, equity: float) -> None:
        """Her turda portfoy degerini tarihceye ekler (report --html grafigi icin)."""
        hist = self.state.setdefault("equity_history", [])
        hist.append([int(time.time() * 1000), round(equity, 2)])
        if len(hist) > 5000:  # dosya sisip durmasin
            del hist[: len(hist) - 5000]

    def _after_stop(self, today: str) -> None:
        """Stop-loss sonrasi korumalar (freqtrade Protections'tan uyarlama):
        cooldown yeni girisi geciktirir, stoploss guard seri stop yenirse
        gunu tamamen kapatir."""
        if self.risk.cooldown_bars > 0:
            wait = self.risk.cooldown_bars * INTERVAL_SEC.get(self.cfg.interval, 3600)
            self.state["cooldown_until"] = time.time() + wait
            self._log(f"cooldown basladi: {self.risk.cooldown_bars} mum giris yok", 0.0)
        self.state["stops_today"] = self.state.get("stops_today", 0) + 1
        if 0 < self.risk.stoploss_guard <= self.state["stops_today"]:
            self.state["halted_day"] = today
            self._log(
                f"STOPLOSS GUARD: bugun {self.state['stops_today']} stop yendi, gun kapatildi",
                0.0,
                notify=True,
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
