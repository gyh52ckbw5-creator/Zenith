#!/usr/bin/env python3
"""Egitim amacli trading bot - komut satiri arayuzu.

Ornekler:
  # Sentetik veriyle backtest (internet gerekmez):
  python run.py backtest --strategy sma --source synthetic

  # Gercek Binance verisiyle backtest (sadece veri okur, hesap gerekmez):
  python run.py backtest --strategy rsi --source binance --symbol BTCUSDT --interval 4h

  # OTOMATIK ARASTIRMA: sembol x strateji x parametre tarar, overfit'i isaretler:
  python run.py scan --symbols BTCUSDT,ETHUSDT --interval 4h

  # OTOMATIK ISLEM (risk yonetimli). Once paper, sonra testnet, en son live:
  python run.py trade --mode paper   --strategy sma --symbol BTCUSDT
  python run.py trade --mode testnet --strategy sma --symbol BTCUSDT
  python run.py trade --mode live    --strategy sma --symbol BTCUSDT --riski-anladim

testnet/live icin BINANCE_API_KEY ve BINANCE_API_SECRET ortam degiskenleri gerekir.
paper ve testnet modlarinda GERCEK PARA YOKTUR. live mod GERCEK PARADIR.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import backtest, data, scanner  # noqa: E402
from bot.exchange import BinanceSpot  # noqa: E402
from bot.risk import RiskConfig  # noqa: E402
from bot.strategies import STRATEGIES  # noqa: E402
from bot.trader import Trader, TraderConfig  # noqa: E402

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_state.json")

UYARI = (
    "*** UYARI: Bu yazilim egitim amaclidir, gercek emir gondermez. ***\n"
    "*** Gecmis performans gelecegi garanti etmez. Kaldiraçli islemler ***\n"
    "*** Turkiye'de SPK duzenlemesine tabidir; sosyal medyadaki 'garanti ***\n"
    "*** kazanc' vaatlerinin buyuk cogunlugu dolandiriciliktir. ***\n"
)


def build_strategy(args: argparse.Namespace):
    cls = STRATEGIES[args.strategy]
    if args.strategy == "sma":
        return cls(fast=args.fast, slow=args.slow)
    if args.strategy == "rsi":
        return cls(period=args.rsi_period)
    return cls()


def get_candles(args: argparse.Namespace) -> list[data.Candle]:
    if args.source == "synthetic":
        return data.synthetic(n=args.bars, seed=args.seed)
    if args.source == "csv":
        return data.load_csv(args.csv)
    return data.fetch_binance(args.symbol, args.interval, args.bars)


def cmd_backtest(args: argparse.Namespace) -> None:
    candles = get_candles(args)
    strategy = build_strategy(args)
    result = backtest.run_backtest(
        candles,
        strategy,
        start_equity=args.equity,
        commission_pct=args.commission,
        slippage_pct=args.slippage,
    )
    print(UYARI)
    print(f"Veri: {args.source}, {len(candles)} mum\n")
    print(result.summary())
    if result.total_return_pct < result.buy_hold_return_pct:
        print("\nNot: Strateji, hicbir sey yapmadan al-ve-tut'un GERISINDE kaldi.")
        print("Sosyal medyada gormedigin gercek iste bu kadar basit olabiliyor.")


def cmd_paper(args: argparse.Namespace) -> None:
    """Sanal cuzdanla canli sinyal takibi. Ctrl+C ile durdurulur."""
    strategy = build_strategy(args)
    state = {"cash": args.equity, "units": 0.0, "log": []}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        print(f"Onceki sanal cuzdan yuklendi: {STATE_FILE}")

    print(UYARI)
    print(f"{args.symbol} {args.interval} izleniyor, strateji: {strategy.name}")
    print(f"Sanal bakiye: {state['cash']:.2f} nakit + {state['units']:.6f} adet\n")

    interval_sec = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}.get(
        args.interval, 3600
    )
    while True:
        try:
            candles = data.fetch_binance(args.symbol, args.interval, 200)
        except Exception as e:
            print(f"Veri cekilemedi ({e}), {interval_sec}s sonra tekrar denenecek")
            time.sleep(interval_sec)
            continue

        target = strategy.target_positions(candles)[-1]
        price = candles[-1].close
        have_position = state["units"] > 0
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        if target == 1 and not have_position:
            state["units"] = state["cash"] / price
            state["cash"] = 0.0
            action = f"SANAL ALIM: {state['units']:.6f} adet @ {price}"
        elif target == 0 and have_position:
            state["cash"] = state["units"] * price
            state["units"] = 0.0
            action = f"SANAL SATIS @ {price}, bakiye: {state['cash']:.2f}"
        else:
            action = f"bekle (fiyat {price}, pozisyon: {'long' if have_position else 'nakit'})"

        equity = state["cash"] + state["units"] * price
        print(f"[{now}] {action} | sanal toplam: {equity:.2f}")
        state["log"].append({"ts": now, "action": action, "equity": equity})
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        time.sleep(interval_sec)


def cmd_scan(args: argparse.Namespace) -> None:
    """Otomatik arastirma: kombinasyonlari tarar, dogrulama verisine gore siralar."""
    print(UYARI)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if args.source == "synthetic":
        def fetch(symbol: str) -> list[data.Candle]:
            return data.synthetic(n=args.bars, seed=abs(hash(symbol)) % 10_000)
    else:
        ex = BinanceSpot(testnet=False)
        def fetch(symbol: str) -> list[data.Candle]:
            return ex.klines(symbol, args.interval, args.bars)

    print(f"Taraniyor: {', '.join(symbols)} ({args.source}, {args.interval}, {args.bars} mum)")
    print("Veri %70 egitim / %30 dogrulama olarak bolundu.\n")
    results = scanner.scan(symbols, fetch)
    for r in results:
        print(r.row())

    pick = scanner.best_pick(results)
    print()
    if pick:
        print(f"Onerilen kombinasyon: {pick.symbol} + {pick.strategy}")
        print("(dogrulama verisinde artida, overfit isareti yok, yeterli islem sayisi)")
        print("Unutma: bu bile gelecegin garantisi DEGIL, sadece elemeyi gecen aday.")
    else:
        print("Hicbir kombinasyon dogrulama elemesini GECEMEDI.")
        print("Dogru cevap bazen 'bugun islem yapma'dir - bot satan kimse bunu soylemez.")


def cmd_trade(args: argparse.Namespace) -> None:
    """Otomatik islem dongusu (paper/testnet/live)."""
    print(UYARI)
    risk = RiskConfig(
        risk_pct_per_trade=args.risk_pct,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_daily_loss_pct=args.max_daily_loss,
    )
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")

    if args.mode == "live":
        if not args.riski_anladim:
            sys.exit(
                "GERCEK PARA modu icin --riski-anladim bayragi zorunlu.\n"
                "Bunu eklemeden once kendine sor: bu strateji testnet'te kac ay artida kaldi?\n"
                "Cevap 'bilmiyorum' ise cevap hayirdir."
            )
        if not api_key or not api_secret:
            sys.exit("live mod icin BINANCE_API_KEY ve BINANCE_API_SECRET gerekli.")
        print(">>> GERCEK PARA MODU AKTIF <<<\n")
        ex = BinanceSpot(api_key, api_secret, testnet=False)
    elif args.mode == "testnet":
        if not api_key or not api_secret:
            sys.exit(
                "testnet icin de anahtar gerekir (para sahtedir, anahtar ucretsizdir):\n"
                "https://testnet.binance.vision adresinden alip BINANCE_API_KEY / "
                "BINANCE_API_SECRET olarak ayarlayin."
            )
        ex = BinanceSpot(api_key, api_secret, testnet=True)
    else:
        ex = BinanceSpot(testnet=False)  # sadece halka acik veri okunur

    cfg = TraderConfig(
        symbol=args.symbol.upper(),
        interval=args.interval,
        mode=args.mode,
        start_equity=args.equity,
        risk=risk,
    )
    Trader(build_strategy(args), cfg, ex).run_forever()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--strategy", choices=sorted(STRATEGIES), default="sma")
        sp.add_argument("--fast", type=int, default=20, help="SMA hizli periyot")
        sp.add_argument("--slow", type=int, default=50, help="SMA yavas periyot")
        sp.add_argument("--rsi-period", type=int, default=14)
        sp.add_argument("--equity", type=float, default=10_000.0, help="Baslangic sanal bakiye")
        sp.add_argument("--symbol", default="BTCUSDT")
        sp.add_argument("--interval", default="1h")
        sp.add_argument("--bars", type=int, default=1000)

    bt = sub.add_parser("backtest", help="Stratejiyi gecmis veride test et")
    common(bt)
    bt.add_argument("--source", choices=["synthetic", "csv", "binance"], default="synthetic")
    bt.add_argument("--csv", help="CSV dosya yolu (--source csv icin)")
    bt.add_argument("--seed", type=int, default=42)
    bt.add_argument("--commission", type=float, default=0.1, help="Islem basina %% komisyon")
    bt.add_argument("--slippage", type=float, default=0.05, help="Islem basina %% kayma")

    pt = sub.add_parser("paper", help="Sanal parayla canli sinyal takibi (emir gondermez)")
    common(pt)

    sc = sub.add_parser("scan", help="Otomatik arastirma: sembol x strateji x parametre tarama")
    sc.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    sc.add_argument("--interval", default="4h")
    sc.add_argument("--bars", type=int, default=1000)
    sc.add_argument("--source", choices=["binance", "synthetic"], default="binance")

    tr = sub.add_parser("trade", help="Otomatik islem dongusu (paper/testnet/live)")
    common(tr)
    tr.add_argument("--mode", choices=["paper", "testnet", "live"], default="paper")
    tr.add_argument("--risk-pct", type=float, default=1.0, help="Islem basina %% risk")
    tr.add_argument("--stop-loss", type=float, default=2.0, help="%% stop-loss")
    tr.add_argument("--take-profit", type=float, default=4.0, help="%% kar al")
    tr.add_argument("--max-daily-loss", type=float, default=5.0, help="Gunluk %% zarar freni")
    tr.add_argument("--riski-anladim", action="store_true",
                    help="live mod onayi: gercek para kaybedebilecegimi anladim")

    args = p.parse_args()
    if args.cmd == "backtest":
        cmd_backtest(args)
    elif args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "trade":
        cmd_trade(args)
    else:
        cmd_paper(args)


if __name__ == "__main__":
    main()
