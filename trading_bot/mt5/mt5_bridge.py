#!/usr/bin/env python3
"""Python -> MetaTrader 5 koprusu: bizim stratejiyle DEMO forex islemi.

NE YAPAR: MT5 demo hesabina baglanir, EURUSD/XAUUSD'yi bizim SMA + trend
filtresi + risk zinciriyle izler, DEMO emri gonderir ve Telegram'a haber
verir. Sen telefondaki MT5 uygulamasina AYNI demo hesabiyla girince
islemler canli onunde gorunur.

NEREDE CALISIR: Sadece Windows + kurulu MT5 terminali (MetaTrader5 paketi
Windows'a ozeldir). Linux/Mac/telefonda calismaz - orada EA (ZenithSmaEA.mq5)
yolunu kullan.

KURULUM (Windows):
  pip install MetaTrader5
  # MT5'i kur, DEMO hesap ac, terminali ACIK birak
  # trading_bot/.env dosyasina ekle:
  #   MT5_LOGIN=12345678
  #   MT5_PASSWORD=demo-sifren
  #   MT5_SERVER=MetaQuotes-Demo
  #   (istege bagli Telegram: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
  python mt5/mt5_bridge.py --symbol EURUSD --interval M15

GUVENLIK: Bu betik SADECE demo icindir. Gercek hesaba baglamak istersen
riski anla; bir yapay zeka koprusune gercek para emri yetkisi vermek
tavsiye edilmez. Kontrol her zaman sende kalsin.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.mt5_logic import decide, lot_from_risk, rates_to_candles, sl_tp_prices  # noqa: E402
from bot.notify import send_telegram  # noqa: E402
from bot.risk import RiskConfig  # noqa: E402
from bot.strategies import SmaCross, TrendFilter  # noqa: E402

try:
    from run import load_env
    load_env()
except Exception:  # noqa: BLE001
    pass

_TF = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--interval", default="M15", choices=sorted(_TF))
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--trend-filter", type=int, default=200, help="0 = kapali")
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--stop-points", type=int, default=2000)
    p.add_argument("--tp-points", type=int, default=4000)
    p.add_argument("--magic", type=int, default=20260709)
    p.add_argument("--allow-live", action="store_true",
                   help="Demo olmayan hesapta calismaya izin ver (ONERILMEZ)")
    args = p.parse_args()

    try:
        import MetaTrader5 as mt5  # noqa: PLC0415 - Windows'a ozel
    except ImportError:
        sys.exit(
            "MetaTrader5 paketi yok. Bu kopru SADECE Windows'ta calisir:\n"
            "  pip install MetaTrader5\n"
            "Linux/Mac/telefonda MQL5 EA (mt5/ZenithSmaEA.mq5) yolunu kullan."
        )

    login = os.environ.get("MT5_LOGIN")
    password = os.environ.get("MT5_PASSWORD")
    server = os.environ.get("MT5_SERVER")
    if not (login and password and server):
        sys.exit("MT5_LOGIN / MT5_PASSWORD / MT5_SERVER .env'de tanimli olmali (DEMO hesap).")

    if not mt5.initialize(login=int(login), password=password, server=server):
        sys.exit(f"MT5 baglantisi basarisiz: {mt5.last_error()}")

    info = mt5.account_info()
    is_demo = info is not None and info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    if not is_demo and not args.allow_live:
        mt5.shutdown()
        sys.exit(
            "GUVENLIK: Bu hesap DEMO gorunmuyor. Kopru varsayilan olarak sadece "
            "demoda calisir. Gercekten gercek hesap istiyorsan --allow-live ekle "
            "(sorumluluk sende)."
        )

    strategy = SmaCross(args.fast, args.slow)
    if args.trend_filter > 0:
        strategy = TrendFilter(strategy, args.trend_filter)
    risk = RiskConfig(risk_pct_per_trade=args.risk_pct,
                      stop_loss_pct=args.stop_points * 0.0001,
                      take_profit_pct=args.tp_points * 0.0001)

    tf = getattr(mt5, f"TIMEFRAME_{args.interval}")
    sym = args.symbol
    mt5.symbol_select(sym, True)
    mode = "DEMO" if is_demo else "CANLI(!)"
    hello = (f"MT5 koprusu basladi [{mode}]: {sym} {args.interval}, "
             f"strateji {strategy.name}, risk %{args.risk_pct}")
    print(hello)
    send_telegram(hello)

    sleep_s = min(_TF[args.interval], 15) * 60  # en fazla mum suresi kadar bekle

    def my_position():
        for pos in mt5.positions_get(symbol=sym) or []:
            if pos.magic == args.magic:
                return pos
        return None

    while True:
        try:
            rates = mt5.copy_rates_from_pos(sym, tf, 0, 400)
            if rates is None or len(rates) < 210:
                time.sleep(sleep_s)
                continue
            candles = rates_to_candles(rates)
            pos = my_position()
            action = decide(candles, pos is not None, strategy)
            tick = mt5.symbol_info_tick(sym)
            si = mt5.symbol_info(sym)

            if action == "buy":
                lots = lot_from_risk(
                    info.equity, args.stop_points, si.point, si.trade_tick_value,
                    si.trade_tick_size, si.volume_step, si.volume_min, si.volume_max,
                    args.risk_pct)
                if lots > 0:
                    sl, tp = sl_tp_prices(tick.ask, risk, si.point, args.stop_points, args.tp_points)
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": lots,
                        "type": mt5.ORDER_TYPE_BUY, "price": tick.ask,
                        "sl": round(sl, si.digits), "tp": round(tp, si.digits),
                        "magic": args.magic, "comment": "Zenith kopru",
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    res = mt5.order_send(req)
                    msg = (f"ALIM {sym} {lots} lot @ {tick.ask}"
                           if res and res.retcode == mt5.TRADE_RETCODE_DONE
                           else f"Alim reddedildi: {getattr(res, 'comment', res)}")
                    print(msg); send_telegram(msg)
            elif action == "sell" and pos is not None:
                req = {
                    "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": pos.volume,
                    "type": mt5.ORDER_TYPE_SELL, "position": pos.ticket,
                    "price": tick.bid, "magic": args.magic, "comment": "Zenith kopru kapat",
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                res = mt5.order_send(req)
                msg = (f"SATIS {sym} @ {tick.bid}"
                       if res and res.retcode == mt5.TRADE_RETCODE_DONE
                       else f"Satis reddedildi: {getattr(res, 'comment', res)}")
                print(msg); send_telegram(msg)
            else:
                print(f"[{time.strftime('%H:%M')}] {sym} bekle "
                      f"(fiyat {tick.bid}, {'pozisyonda' if pos else 'nakitte'})")
        except KeyboardInterrupt:
            print("\nDurduruldu.")
            break
        except Exception as e:  # noqa: BLE001 - kopru dongusu olmesin
            print(f"Hata: {e}")
        time.sleep(sleep_s)

    mt5.shutdown()


if __name__ == "__main__":
    main()
