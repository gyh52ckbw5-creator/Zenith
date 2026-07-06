#!/usr/bin/env python3
"""Egitim amacli trading bot - komut satiri arayuzu.

Ornekler:
  # Sentetik veriyle backtest (internet gerekmez):
  python run.py backtest --strategy sma --source synthetic

  # Gercek Binance verisiyle backtest (sadece veri okur, hesap gerekmez):
  python run.py backtest --strategy rsi --source binance --symbol BTCUSDT --interval 4h

  # Paper trading: SANAL para ile canli fiyati izler, karar verir, dosyaya yazar:
  python run.py paper --strategy sma --symbol BTCUSDT --interval 1h

Bu arac hicbir sekilde gercek emir GONDERMEZ.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import backtest, data  # noqa: E402
from bot.strategies import STRATEGIES  # noqa: E402

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

    args = p.parse_args()
    if args.cmd == "backtest":
        cmd_backtest(args)
    else:
        cmd_paper(args)


if __name__ == "__main__":
    main()
