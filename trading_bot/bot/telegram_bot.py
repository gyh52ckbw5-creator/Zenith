"""Iki yonlu Telegram: botu telefondan komutla yonet.

Komutlar (bota Telegram'dan yazilir):
  /durum            sanal portfoy ozeti
  /fiyat SEMBOL     guncel fiyat (BTCUSDT, EURUSD, XAUUSD...)
  /analiz           hizli piyasa taramasi (kripto+forex+altin, gunluk)
  /rapor            son kapanan islemler (trades_*.csv)
  /yardim           bu liste

GUVENLIK: yalnizca TELEGRAM_CHAT_ID'deki kisiye cevap verilir; baska
herkesin mesaji sessizce yok sayilir. Bu servis islem ACMAZ/KAPATMAZ -
sadece bilgi verir; emir yetkisi bilerek verilmemistir.

Not: Telegram bir token icin tek getUpdates dinleyicisine izin verir;
bu servis calisirken `notify-test`in sohbet kesfi bos donebilir (normal).
"""

from __future__ import annotations

import glob
import json
import os
import time
import urllib.parse
import urllib.request

from .data import fetch_yahoo, yahoo_symbol
from .exchange import BinanceSpot
from .scanner import best_pick, scan

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HELP_TEXT = (
    "Zenith bot komutlari:\n"
    "/durum - sanal portfoy ozeti\n"
    "/fiyat SEMBOL - guncel fiyat (ör. /fiyat XAUUSD)\n"
    "/analiz - hizli piyasa taramasi (biraz surer)\n"
    "/derin SEMBOL - tek sembol derin analiz (rejim, trend, momentum, seviyeler)\n"
    "/montecarlo SEMBOL - sonuc ne kadar sansa bagli? (binlerce simulasyon)\n"
    "/rapor - son kapanan islemler\n"
    "/yardim - bu liste\n"
    "(Egitim amaclidir; islem acma/kapama komutu bilerek yoktur.)"
)

ANALYZE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "EURUSD", "XAUUSD"]


class TelegramCommander:
    def __init__(self) -> None:
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not self.token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekli (.env)")
        self.offset = 0
        self.ex = BinanceSpot(testnet=False)

    # -- Telegram API ----------------------------------------------------
    def _api(self, method: str, http_timeout: int = 15, **params) -> dict:
        body = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}", data=body, method="POST"
        )
        with urllib.request.urlopen(req, timeout=http_timeout) as resp:
            return json.loads(resp.read().decode())

    def send(self, text: str) -> None:
        self._api("sendMessage", chat_id=self.chat_id, text=text[:4000])

    def poll(self) -> list[dict]:
        # timeout=50: Telegram long-poll (mesaj gelene kadar 50 sn bekler)
        data = self._api("getUpdates", http_timeout=60, offset=self.offset, timeout=50)
        return data.get("result", [])

    # -- komutlar (saf metin -> metin; test edilebilir) --------------------
    def handle(self, text: str) -> str:
        parts = text.strip().split()
        cmd = parts[0].lower().lstrip("/").split("@")[0] if parts else ""
        try:
            if cmd == "durum":
                return self._durum()
            if cmd == "fiyat" and len(parts) > 1:
                return self._fiyat(parts[1].upper())
            if cmd == "analiz":
                return self._analiz()
            if cmd == "derin":
                return self._derin(parts[1].upper() if len(parts) > 1 else "XAUUSD")
            if cmd == "montecarlo":
                return self._montecarlo(parts[1].upper() if len(parts) > 1 else "XAUUSD")
            if cmd == "rapor":
                return self._rapor()
        except Exception as exc:  # noqa: BLE001 - hata da cevap olarak gitsin
            return f"Hata: {exc}"
        return HELP_TEXT

    def _fiyat(self, symbol: str) -> str:
        if symbol.endswith("USDT"):
            price = self.ex.price(symbol)
        else:
            price = fetch_yahoo(yahoo_symbol(symbol), "1d", 2)[-1].close
        return f"{symbol}: {price:,.4f}"

    def _durum(self) -> str:
        files = sorted(glob.glob(os.path.join(_BASE_DIR, "trader_state_*.json")))
        if not files:
            return "Henuz calisan bot verisi yok."
        lines, total = [], 0.0
        for path in files:
            try:
                with open(path, encoding="utf-8") as f:
                    st = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            fallback = os.path.basename(path).replace("trader_state_", "").replace(".json", "")
            sym = st.get("symbol", fallback)
            mode = st.get("mode", "paper")
            hist = st.get("equity_history", [])
            eq = hist[-1][1] if hist else st.get("cash", 0.0)
            total += eq
            pos = "pozisyonda" if st.get("qty", 0) > 0 else "nakitte"
            lines.append(f"{sym}[{mode}]: {eq:,.2f} ({pos})")
        return "Sanal portfoy:\n" + "\n".join(lines) + f"\nToplam: {total:,.2f}"

    def _analiz(self) -> str:
        def fetch(sym: str):
            if sym.endswith("USDT"):
                return self.ex.klines(sym, "1d", 1000)
            return fetch_yahoo(yahoo_symbol(sym), "1d", 1000)

        results = scan(ANALYZE_SYMBOLS, fetch)
        lines = ["Hizli tarama (gunluk):"]
        lines += ["  " + r.row() for r in results[:3]]
        pick = best_pick(results)
        lines.append(
            f"Aday: {pick.symbol} + {pick.strategy}" if pick else "Elemeyi gecen aday yok."
        )
        return "\n".join(lines)

    def _derin(self, symbol: str) -> str:
        from .analyst import full_report  # tembel: agir modul, ihtiyacta yuklensin

        if symbol.endswith("USDT"):
            candles = self.ex.klines(symbol, "1d", 1000)
        else:
            candles = fetch_yahoo(yahoo_symbol(symbol), "1d", 1000)
        return full_report(symbol, candles)

    def _montecarlo(self, symbol: str) -> str:
        from .montecarlo import monte_carlo  # tembel yukleme

        if symbol.endswith("USDT"):
            candles = self.ex.klines(symbol, "1d", 1000)
        else:
            candles = fetch_yahoo(yahoo_symbol(symbol), "1d", 1000)
        from .backtest import run_backtest
        from .strategies import SmaCross

        res = run_backtest(candles, SmaCross(), stop_loss_pct=3.0, take_profit_pct=9.0, cooldown_bars=5)
        mc = monte_carlo([t.pnl_pct for t in res.trades], trials=2000)
        head = f"{symbol} gecmis getiri {res.total_return_pct:+.1f}% ({res.n_trades} islem)\n"
        return head + (mc.summary() if mc else "Monte Carlo icin en az 10 islem gerekir.")

    def _rapor(self) -> str:
        rows: list[str] = []
        for path in sorted(glob.glob(os.path.join(_BASE_DIR, "trades_*.csv"))):
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.read().strip().splitlines()[1:]
                rows += lines[-5:]
            except OSError:
                continue
        if not rows:
            return "Henuz kapanan islem yok."
        out = "Son islemler (zaman,mod,sembol,giris,cikis,k/z%,neden):\n" + "\n".join(rows[-10:])
        try:
            from .mathrisk import format_stats, trade_stats

            pnls = [float(r.split(",")[5]) for r in rows if len(r.split(",")) >= 6]
            stats = trade_stats(pnls)
            if stats:
                out += "\n\n" + format_stats(stats)
        except (ValueError, IndexError):
            pass
        return out

    # -- dongu -------------------------------------------------------------
    def run_forever(self) -> None:
        print("Telegram komut servisi basladi. Botuna /yardim yaz.")
        self.send("Komut servisi aktif! /yardim yazarak baslayabilirsin.")
        while True:
            try:
                for update in self.poll():
                    self.offset = update["update_id"] + 1
                    msg = update.get("message") or {}
                    chat = str((msg.get("chat") or {}).get("id", ""))
                    text = msg.get("text", "")
                    if chat != str(self.chat_id) or not text:
                        continue  # yabancilara cevap yok
                    print(f"[komut] {text}")
                    self.send(self.handle(text))
            except Exception as exc:  # noqa: BLE001 - ag hatasi donguyu oldurmesin
                print(f"telegram hatasi: {exc}, 10s sonra tekrar")
                time.sleep(10)
