#!/usr/bin/env python3
"""Python -> MetaTrader 5 koprusu: demo varsayilanli forex islemi.

NE YAPAR: MT5 hesabina baglanir, EURUSD/XAUUSD'yi SMA + trend filtresi +
risk zinciriyle izler, emir gonderir ve Telegram'a haber verir. Varsayilan
mod demo hesabidir. Canli mod; acik bayrak, tam hesap numarasi ve yazili
risk onayi birlikte verilmeden baslamaz.

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

GUVENLIK: Once --preflight-only kullan. Canli mod kâr garantisi vermez;
kontrol her zaman hesap sahibinde kalmalidir.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.mt5_logic import (  # noqa: E402
    broker_stops_valid,
    daily_loss_exceeded,
    decide,
    latest_closed_bar_ts,
    lot_from_risk,
    margin_within_limit,
    rates_to_candles,
    sl_tp_prices,
    spread_points,
    tick_is_fresh,
    weekend_entry_blocked,
)
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
    p.add_argument("--max-daily-loss", type=float, default=3.0,
                   help="Gunluk equity dususu bu yuzdeye ulasinca pozisyonu kapat ve gunu durdur")
    p.add_argument("--max-spread-points", type=float, default=50.0,
                   help="Yeni alim icin izin verilen en yuksek spread (broker puani)")
    p.add_argument("--max-tick-age", type=float, default=30.0,
                   help="Yeni alim icin kotasyonun en fazla yasi (saniye)")
    p.add_argument("--max-margin-pct", type=float, default=20.0,
                   help="Tek pozisyonun baglayabilecegi azami equity yuzdesi")
    p.add_argument("--min-margin-level", type=float, default=300.0,
                   help="Yeni alim icin gereken asgari hesap margin level yuzdesi")
    p.add_argument("--deviation", type=int, default=20,
                   help="Emirde izin verilen azami fiyat sapmasi (puan)")
    p.add_argument("--friday-cutoff-utc", type=int, default=18,
                   help="Cuma bu UTC saatinden sonra yeni pozisyon acma")
    p.add_argument("--hold-weekend", action="store_true",
                   help="Cuma/hafta sonu yeni girise izin ver (onerilmez)")
    p.add_argument("--account-mode", choices=("demo", "live"), default="demo",
                   help="Beklenen hesap turu; varsayilan demo")
    p.add_argument("--live-account", type=int, default=0,
                   help="Canli modda izin verilen TAM MT5 hesap numarasi")
    p.add_argument("--live-ack", default="",
                   help="Canli mod icin tam olarak CANLI_RISKI_KABUL yaz")
    p.add_argument("--preflight-only", action="store_true",
                   help="Baglanti/hesap/sembol kontrollerini yap, emir dongusunu baslatma")
    p.add_argument("--magic", type=int, default=20260709)
    p.add_argument("--allow-live", action="store_true",
                   help="Canli modun birinci acik guvenlik kilidi")
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

    # Once ACIK terminale baglan: MT5 zaten demo hesaba girmisse sifre gerekmez.
    ok = mt5.initialize()
    # Terminal kapali ya da baska hesaptaysa, .env kimlik bilgileriyle dene.
    if (not ok or mt5.account_info() is None) and login and password and server:
        ok = mt5.initialize(login=int(login), password=password, server=server)
    if not ok or mt5.account_info() is None:
        sys.exit(
            f"MT5 baglantisi basarisiz: {mt5.last_error()}\n"
            "Cozum: MT5 uygulamasi ACIK ve demo hesaba GIRIS YAPMIS olsun "
            "(ust barda hesap numaran gorunur), sonra tekrar calistir.\n"
            "Alternatif: .env'e dogru MT5_LOGIN / MT5_PASSWORD / MT5_SERVER yaz."
        )

    info = mt5.account_info()
    is_demo = info is not None and info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    if args.account_mode == "demo" and not is_demo:
        mt5.shutdown()
        sys.exit(
            "GUVENLIK: --account-mode demo secili ama acik MT5 hesabi demo degil."
        )
    if args.account_mode == "live":
        live_ok = (
            not is_demo
            and args.allow_live
            and args.live_account == int(info.login)
            and args.live_ack == "CANLI_RISKI_KABUL"
        )
        if not live_ok:
            mt5.shutdown()
            sys.exit(
                "GUVENLIK: canli mod icin birlikte sunlar gerekir:\n"
                "  --account-mode live --allow-live\n"
                f"  --live-account {int(info.login)}\n"
                "  --live-ack CANLI_RISKI_KABUL"
            )

    strategy = SmaCross(args.fast, args.slow)
    if args.trend_filter > 0:
        strategy = TrendFilter(strategy, args.trend_filter)
    risk = RiskConfig(
        risk_pct_per_trade=args.risk_pct,
        stop_loss_pct=args.stop_points * 0.0001,
        take_profit_pct=args.tp_points * 0.0001,
        max_daily_loss_pct=args.max_daily_loss,
    )
    risk.validate()
    if args.stop_points <= 0 or args.tp_points <= 0:
        sys.exit("--stop-points ve --tp-points pozitif olmali.")
    if args.max_spread_points <= 0 or args.max_tick_age <= 0:
        sys.exit("--max-spread-points ve --max-tick-age pozitif olmali.")
    if not (0 < args.max_margin_pct <= 100) or args.min_margin_level <= 0:
        sys.exit("--max-margin-pct 0-100, --min-margin-level pozitif olmali.")
    if args.deviation < 0 or not (0 <= args.friday_cutoff_utc <= 23):
        sys.exit("--deviation negatif olamaz; --friday-cutoff-utc 0-23 olmali.")

    tf = getattr(mt5, f"TIMEFRAME_{args.interval}")
    sym = args.symbol
    if not mt5.symbol_select(sym, True):
        mt5.shutdown()
        sys.exit(f"{sym} Market Watch'a eklenemedi: {mt5.last_error()}")
    terminal = mt5.terminal_info()
    si0 = mt5.symbol_info(sym)
    if terminal is None or not terminal.trade_allowed:
        mt5.shutdown()
        sys.exit("MT5 terminalinde Algo Trading/otomatik islem izni kapali.")
    if not info.trade_allowed or not info.trade_expert:
        mt5.shutdown()
        sys.exit("Hesap, otomatik uzman islemlerine izin vermiyor.")
    allowed_modes = {
        mt5.SYMBOL_TRADE_MODE_FULL,
        mt5.SYMBOL_TRADE_MODE_LONGONLY,
    }
    if si0 is None or si0.trade_mode not in allowed_modes:
        mt5.shutdown()
        sys.exit(f"{sym} yeni long isleme acik degil.")
    mode = "DEMO" if is_demo else "CANLI(!)"
    hello = (f"MT5 koprusu basladi [{mode}]: {sym} {args.interval}, "
             f"strateji {strategy.name}, risk %{args.risk_pct}, "
             f"gunluk fren %{args.max_daily_loss}, max spread {args.max_spread_points:g} puan")
    print(hello)
    send_telegram(hello)
    if args.preflight_only:
        print(
            f"PREFLIGHT OK: hesap={int(info.login)} mod={mode} sembol={sym} "
            f"equity={float(info.equity):.2f} margin_level={float(info.margin_level):.1f}"
        )
        mt5.shutdown()
        return

    sleep_s = min(_TF[args.interval], 15) * 60  # en fazla mum suresi kadar bekle
    state_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f".mt5_bridge_state_{sym}_{args.magic}.json",
    )

    def load_safety_state() -> dict:
        if not os.path.exists(state_file):
            return {}
        try:
            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError) as exc:
            mt5.shutdown()
            sys.exit(
                f"GUVENLIK: MT5 durum dosyasi okunamadi ({state_file}): {exc}. "
                "Dosyayi incelemeden bot yeniden baslatilmadi."
            )

    def save_safety_state(state: dict) -> None:
        tmp = state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, state_file)

    safety = load_safety_state()

    def filling_mode(si):
        """SYMBOL_FILLING_* bit maskesini ORDER_FILLING_* degerine cevir."""
        if si.filling_mode & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        if si.filling_mode & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def my_position():
        for pos in mt5.positions_get(symbol=sym) or []:
            if pos.magic == args.magic:
                return pos
        return None

    def close_position(pos, tick, reason: str) -> bool:
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL, "position": pos.ticket,
            "price": tick.bid, "magic": args.magic, "comment": f"Zenith {reason}"[:31],
            "deviation": args.deviation,
            "type_filling": filling_mode(si),
        }
        res = mt5.order_send(req)
        ok = bool(res and res.retcode == mt5.TRADE_RETCODE_DONE)
        msg = (
            f"SATIS {sym} @ {tick.bid} ({reason})"
            if ok else f"Satis reddedildi ({reason}): {getattr(res, 'comment', res)}"
        )
        print(msg)
        send_telegram(msg)
        return ok

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
            current_info = mt5.account_info()
            if tick is None or si is None or current_info is None:
                raise RuntimeError(f"MT5 hesap/sembol/tick bilgisi eksik: {mt5.last_error()}")

            today = time.strftime("%Y-%m-%d")
            if safety.get("day") != today:
                safety = {
                    "day": today,
                    "day_start_equity": float(current_info.equity),
                    "halted_day": "",
                    "last_closed_bar_ts": safety.get("last_closed_bar_ts", 0),
                }
                save_safety_state(safety)

            if daily_loss_exceeded(
                float(safety["day_start_equity"]),
                float(current_info.equity),
                args.max_daily_loss,
            ):
                first_halt = safety.get("halted_day") != today
                safety["halted_day"] = today
                save_safety_state(safety)
                if pos is not None:
                    close_position(pos, tick, "gunluk zarar freni")
                if first_halt:
                    msg = (
                        f"KILL SWITCH {sym}: gunluk equity kaybi "
                        f"%{args.max_daily_loss:g} sinirina ulasti; bugun yeni emir yok."
                    )
                    print(msg)
                    send_telegram(msg)
                time.sleep(sleep_s)
                continue

            closed_ts = latest_closed_bar_ts(candles)
            is_new_closed_bar = closed_ts > int(safety.get("last_closed_bar_ts", 0))
            if is_new_closed_bar:
                # Karar reddedilse bile ayni kapanmis mumda tekrar emir denenmez.
                safety["last_closed_bar_ts"] = closed_ts
                save_safety_state(safety)

            if action == "buy":
                if safety.get("halted_day") == today:
                    print(f"[{time.strftime('%H:%M')}] {sym} gunluk fren aktif, alim yok")
                    time.sleep(sleep_s)
                    continue
                if not is_new_closed_bar:
                    print(f"[{time.strftime('%H:%M')}] {sym} yeni kapanmis mum yok, alim yok")
                    time.sleep(sleep_s)
                    continue
                if not tick_is_fresh(tick.time, max_age_seconds=args.max_tick_age):
                    print(f"[{time.strftime('%H:%M')}] {sym} kotasyon eski, alim yok")
                    time.sleep(sleep_s)
                    continue
                if not args.hold_weekend and weekend_entry_blocked(
                    tick.time, args.friday_cutoff_utc
                ):
                    print(f"[{time.strftime('%H:%M')}] {sym} hafta sonu/gap korumasi, alim yok")
                    time.sleep(sleep_s)
                    continue
                if 0 < current_info.margin and current_info.margin_level < args.min_margin_level:
                    print(
                        f"[{time.strftime('%H:%M')}] margin level "
                        f"%{current_info.margin_level:.1f} (min %{args.min_margin_level:g}), alim yok"
                    )
                    time.sleep(sleep_s)
                    continue
                current_spread = spread_points(tick.bid, tick.ask, si.point)
                if current_spread > args.max_spread_points:
                    print(
                        f"[{time.strftime('%H:%M')}] {sym} spread {current_spread:.1f} puan "
                        f"(limit {args.max_spread_points:g}), alim yok"
                    )
                    time.sleep(sleep_s)
                    continue
                lots = lot_from_risk(
                    current_info.equity, args.stop_points, si.point, si.trade_tick_value,
                    si.trade_tick_size, si.volume_step, si.volume_min, si.volume_max,
                    args.risk_pct)
                if lots > 0:
                    sl, tp = sl_tp_prices(tick.ask, risk, si.point, args.stop_points, args.tp_points)
                    if not broker_stops_valid(
                        tick.ask, sl, tp, si.point, int(si.trade_stops_level)
                    ):
                        print(
                            f"{sym}: SL/TP broker minimum mesafesini karsilamiyor "
                            f"({int(si.trade_stops_level)} puan), alim yok"
                        )
                        time.sleep(sleep_s)
                        continue
                    required_margin = mt5.order_calc_margin(
                        mt5.ORDER_TYPE_BUY, sym, lots, tick.ask
                    )
                    if required_margin is None or not margin_within_limit(
                        float(required_margin), float(current_info.equity), args.max_margin_pct
                    ):
                        print(
                            f"{sym}: gereken margin {required_margin}, limit equity'nin "
                            f"%{args.max_margin_pct:g}; alim yok"
                        )
                        time.sleep(sleep_s)
                        continue
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": lots,
                        "type": mt5.ORDER_TYPE_BUY, "price": tick.ask,
                        "sl": round(sl, si.digits), "tp": round(tp, si.digits),
                        "magic": args.magic, "comment": "Zenith kopru",
                        "deviation": args.deviation,
                        "type_filling": filling_mode(si),
                    }
                    check = mt5.order_check(req)
                    if check is None or check.retcode != 0:
                        msg = f"Alim on kontrol reddi: {getattr(check, 'comment', check)}"
                        print(msg)
                        send_telegram(msg)
                        time.sleep(sleep_s)
                        continue
                    res = mt5.order_send(req)
                    msg = (f"ALIM {sym} {lots} lot @ {tick.ask}"
                           if res and res.retcode == mt5.TRADE_RETCODE_DONE
                           else f"Alim reddedildi: {getattr(res, 'comment', res)}")
                    print(msg); send_telegram(msg)
            elif action == "sell" and pos is not None and is_new_closed_bar:
                close_position(pos, tick, "strateji sinyali")
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
