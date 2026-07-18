#!/usr/bin/env python3
"""Egitim amacli trading bot - komut satiri arayuzu.

Komutlar (ayrintili kurulum sirasi icin: KURULUM.md):
  backtest     Stratejiyi gecmis veride test et (--stop-loss vb. ile risk simulasyonu)
  chart        Backtest + equity egrisi grafikli HTML rapor
  scan         Sembol x strateji x parametre tarama, overfit isaretlemeli
  walkforward  Stratejiyi ardisik zaman dilimlerinde dogrula (profesyonel standart)
  optimize     Rastgele parametre arama, walk-forward puanlamali (hyperopt-lite)
  analyze      Surekli analiz: duzenli tarar, Telegram'a rapor atar
  trade        Otomatik islem dongusu: paper / testnet / live (risk yonetimli)
  report       Sanal portfoy durumu (--html ile grafik)
  readiness    Demo/testnet gunlugunden canliya hazirlik kapisi + grafik
  notify-test  Telegram baglantisini kur ve test et

Ornekler:
  python run.py backtest --strategy sma --source synthetic          # internet gerekmez
  python run.py backtest --strategy sma --source yahoo --symbol XAUUSD --interval 1d
  python run.py scan --symbols BTCUSDT,ETHUSDT,XAUUSD --interval 1d
  python run.py optimize --strategy donchian --source binance --symbol BTCUSDT
  python run.py analyze --once
  python run.py trade --mode paper --symbols BTCUSDT,ETHUSDT --strategy sma
  python run.py trade --mode live  --symbol BTCUSDT --riski-anladim  # GERCEK PARA

Sembol kurali: USDT ile bitenler Binance'ten (kripto), digerleri Yahoo'dan
(EURUSD, XAUUSD/GOLD, USDTRY, hisse...). testnet/live icin BINANCE_API_KEY ve
BINANCE_API_SECRET gerekir (trading_bot/.env). live mod GERCEK PARADIR.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import backtest, data, optimize as optimize_mod, scanner  # noqa: E402
from bot.ai_analyst import ai_available, ai_comment  # noqa: E402
from bot.exchange import BinanceSpot  # noqa: E402
from bot.risk import RiskConfig  # noqa: E402
from bot.strategies import STRATEGIES, TrendFilter  # noqa: E402
from bot.notify import discover_chat_ids, send_telegram, telegram_configured  # noqa: E402
from bot.trader import Trader, TraderConfig, run_many  # noqa: E402

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_state.json")


def load_env(path: str = "") -> None:
    """trading_bot/.env dosyasindaki KEY=VALUE satirlarini ortama yukler.

    Var olan ortam degiskenlerini EZMEZ. .env git'e gitmez (.gitignore'da).
    """
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

UYARI = (
    "*** UYARI: Bu yazilim egitim amaclidir, gercek emir gondermez. ***\n"
    "*** Gecmis performans gelecegi garanti etmez. Kaldiraçli islemler ***\n"
    "*** Turkiye'de SPK duzenlemesine tabidir; sosyal medyadaki 'garanti ***\n"
    "*** kazanc' vaatlerinin buyuk cogunlugu dolandiriciliktir. ***\n"
)


def build_strategy(args: argparse.Namespace):
    cls = STRATEGIES[args.strategy]
    if args.strategy in ("sma", "ema"):
        strat = cls(fast=args.fast, slow=args.slow)
    elif args.strategy == "rsi":
        strat = cls(period=args.rsi_period)
    else:
        strat = cls()
    if getattr(args, "trend_filter", 0) > 0:
        strat = TrendFilter(strat, period=args.trend_filter)
    return strat


def get_candles(args: argparse.Namespace) -> list[data.Candle]:
    if args.source == "synthetic":
        return data.synthetic(n=args.bars, seed=args.seed)
    if args.source == "csv":
        return data.load_csv(args.csv)
    if args.source == "yahoo":
        return data.fetch_yahoo(data.yahoo_symbol(args.symbol), args.interval, args.bars)
    return data.fetch_binance(args.symbol, args.interval, args.bars)


SYMBOL_PRESETS = {
    "FOREX": "EURUSD,GBPUSD,USDJPY,USDTRY,XAUUSD",
    "KRIPTO": "BTCUSDT,ETHUSDT,SOLUSDT",
    "HEPSI": "BTCUSDT,ETHUSDT,EURUSD,GBPUSD,XAUUSD",
}


def parse_symbols(text: str) -> list[str]:
    """Virgullu listeyi ayristirir; FOREX/KRIPTO/HEPSI kisayollarini acar."""
    out: list[str] = []
    for part in text.split(","):
        s = part.strip().upper()
        if not s:
            continue
        out.extend(SYMBOL_PRESETS.get(s, s).split(","))
    return out


def smart_fetch(interval: str, bars: int):
    """Sembole gore dogru kaynagi secen veri cekici: USDT ile bitenler
    Binance'ten (kripto), digerleri Yahoo'dan (forex/altin/hisse)."""
    ex = BinanceSpot(testnet=False)

    def fetch(symbol: str) -> list[data.Candle]:
        if symbol.upper().endswith("USDT"):
            return ex.klines(symbol, interval, bars)
        return data.fetch_yahoo(data.yahoo_symbol(symbol), interval, bars)

    return fetch


def run_bt(args: argparse.Namespace, candles, strategy):
    """backtest/chart icin ortak kosum: risk bayraklarini da simule eder."""
    return backtest.run_backtest(
        candles,
        strategy,
        start_equity=args.equity,
        commission_pct=args.commission,
        slippage_pct=args.slippage,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        trailing_stop_pct=args.trailing_stop,
        cooldown_bars=args.cooldown,
        risk_pct_per_trade=args.risk_pct,
        max_position_pct=args.max_position,
    )


def cmd_backtest(args: argparse.Namespace) -> None:
    candles = get_candles(args)
    strategy = build_strategy(args)
    result = run_bt(args, candles, strategy)
    print(UYARI)
    print(f"Veri: {args.source}, {len(candles)} mum\n")
    print(result.summary())
    if result.total_return_pct < result.buy_hold_return_pct:
        print("\nNot: Strateji, hicbir sey yapmadan al-ve-tut'un GERISINDE kaldi.")
        print("Sosyal medyada gormedigin gercek iste bu kadar basit olabiliyor.")


def cmd_paper(args: argparse.Namespace) -> None:
    """Sanal cuzdanla canli sinyal takibi. Ctrl+C ile durdurulur."""
    print("Not: `paper` eski/basit moddur (risk yonetimi yok). Onerilen:")
    print("  python run.py trade --mode paper --symbol", args.symbol, "\n")
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

        # son mum hala olusuyor: sinyal kapanmis mumlardan, fiyat guncelden
        target = strategy.target_positions(candles[:-1])[-1]
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
    symbols = parse_symbols(args.symbols)
    if args.source == "synthetic":
        def fetch(symbol: str) -> list[data.Candle]:
            return data.synthetic(n=args.bars, seed=abs(hash(symbol)) % 10_000)
    else:  # USDT ile bitenler Binance'ten, digerleri (EURUSD, XAUUSD...) Yahoo'dan
        fetch = smart_fetch(args.interval, args.bars)

    print(f"Taraniyor: {', '.join(symbols)} ({args.source}, {args.interval}, {args.bars} mum)")
    print("Veri %70 egitim / %30 dogrulama olarak bolundu.\n")
    results = scanner.scan(
        symbols,
        fetch,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        trailing_stop_pct=args.trailing_stop,
        cooldown_bars=args.cooldown,
        risk_pct_per_trade=args.risk_pct,
        max_position_pct=args.max_position,
    )
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
        trailing_stop_pct=args.trailing_stop,
        atr_stop_mult=args.atr_stop,
        cooldown_bars=args.cooldown,
        stoploss_guard=args.stoploss_guard,
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

    symbols = parse_symbols(args.symbols or args.symbol)
    if telegram_configured():
        print("Telegram bildirimi AKTIF: islemler telefonuna gidecek.\n")
    else:
        print("Telegram bildirimi kapali (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ayarlanmamis).\n")
    traders = [
        Trader(
            build_strategy(args),
            TraderConfig(
                symbol=sym,
                interval=args.interval,
                mode=args.mode,
                start_equity=args.equity / len(symbols),  # paper: sanal bakiye esit bolunur
                risk=risk,
                news_filter=args.news_filter,
                mtf_daily=args.daily_trend,
                poll_seconds=args.poll_seconds,
            ),
            ex,
        )
        for sym in symbols
    ]
    run_many(traders)


def cmd_walkforward(args: argparse.Namespace) -> None:
    """Walk-forward testi: strateji ardisik zaman dilimlerinin kacinda ayakta?"""
    print(UYARI)
    candles = get_candles(args)
    strategy = build_strategy(args)
    returns = scanner.walk_forward(
        candles, strategy, segments=args.segments,
        stop_loss_pct=args.stop_loss, take_profit_pct=args.take_profit,
        trailing_stop_pct=args.trailing_stop, cooldown_bars=args.cooldown,
        risk_pct_per_trade=args.risk_pct, max_position_pct=args.max_position,
    )
    print(f"Strateji: {strategy.name}, veri: {args.source} ({len(candles)} mum), "
          f"{args.segments} dilim\n")
    positive = 0
    for i, r in enumerate(returns, 1):
        bar = "#" * min(40, int(abs(r)))
        sign = "+" if r >= 0 else "-"
        if r >= 0:
            positive += 1
        print(f"  Dilim {i}: {r:+8.2f}%  {sign}{bar}")
    print(f"\nArtida biten dilim: {positive}/{len(returns)}")
    if positive == len(returns):
        print("Tum dilimlerde artida - umut verici ama yine de garanti degil.")
    elif positive >= len(returns) * 0.6:
        print("Cogu dilimde ayakta kalmis; derinlemesine incelemeye deger.")
    else:
        print("Dilimlerin cogunda zarar: tek bolmede iyi gorunduyse SANS'ti.")
        print("Gercek parayla bu stratejiyi calistirmak icin hicbir neden yok.")


def cmd_report(args: argparse.Namespace) -> None:
    """trader_state_*.json dosyalarindan portfoy durumu raporu."""
    import glob

    base = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(base, "trader_state_*.json")))
    if not files:
        sys.exit("Henuz islem durumu yok. Once `trade` komutunu calistir.")
    ex = BinanceSpot(testnet=False)
    total = 0.0
    histories: dict[str, list] = {}
    print(f"{'Sembol':<10} {'Nakit':>10} {'Adet':>12} {'Deger':>10} {'Pozisyon'}")
    for path in files:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
        fallback = os.path.basename(path).replace("trader_state_", "").replace(".json", "")
        symbol = st.get("symbol", fallback)
        mode = st.get("mode", "paper")
        label = f"{symbol}[{mode}]"
        qty = st.get("qty", 0.0)
        value = 0.0
        pos = "nakitte"
        if qty > 0:
            try:
                price = ex.price(symbol)
                value = qty * price
                entry = st.get("entry_price", 0.0)
                pnl = 100.0 * (price / entry - 1) if entry else 0.0
                pos = f"long @ {entry} (k/z {pnl:+.2f}%)"
            except Exception:
                pos = "long (fiyat alinamadi)"
        equity = st.get("cash", 0.0) + value
        total += equity
        print(f"{label:<18} {st.get('cash', 0.0):>10.2f} {qty:>12.6f} {value:>10.2f} {pos}")
        buys = sum(1 for line in st.get("log", []) if "ALIM" in line)
        sells = sum(1 for line in st.get("log", []) if "SATIS" in line)
        print(f"{'':<10} islem gecmisi: {buys} alim, {sells} satis")
        histories[label] = st.get("equity_history", [])
    print(f"\nToplam portfoy degeri: {total:.2f}")

    # istatistik kosesi: kapanan islemlerden beklenti/Kelly/iflas olasiligi
    pnls: list[float] = []
    for path in glob.glob(os.path.join(base, "trades_*.csv")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f.read().strip().splitlines()[1:]:
                    parts = line.split(",")
                    if len(parts) >= 6:
                        pnls.append(float(parts[5]))
        except (OSError, ValueError):
            continue
    if pnls:
        from bot.mathrisk import format_stats, trade_stats

        stats = trade_stats(pnls)
        if stats:
            print()
            print(format_stats(stats))

    if args.html:
        from bot.report_html import render_live_html

        out = os.path.join(base, "report_portfoy.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(render_live_html(histories, "Zenith portfoy tarihcesi"))
        print(f"HTML grafik yazildi: {out}")


def cmd_chart(args: argparse.Namespace) -> None:
    """Backtest calistirir ve equity egrisi grafikli HTML rapor uretir."""
    from bot.report_html import render_html

    candles = get_candles(args)
    strategy = build_strategy(args)
    result = run_bt(args, candles, strategy)
    title = f"{args.symbol if args.source in ('binance', 'yahoo') else args.source} " \
            f"{args.interval} - {result.strategy}"
    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"report_{args.symbol}_{args.strategy}.html",
    )
    with open(out, "w", encoding="utf-8") as f:
        f.write(render_html(result, candles, title))
    print(UYARI)
    print(result.summary())
    print(f"\nHTML rapor yazildi: {out}")
    print("Tarayicida ac: mavi cizgi strateji, gri cizgi al-ve-tut kiyasi.")


def cmd_optimize(args: argparse.Namespace) -> None:
    """Rastgele parametre arama, walk-forward puanlamali (hyperopt-lite)."""
    if args.strategy == "hold":
        sys.exit("hold stratejisinin parametresi yok; sma/ema/rsi/donchian/bollinger/macd sec.")
    print(UYARI)
    candles = get_candles(args)
    results = optimize_mod.optimize(
        candles, args.strategy,
        trials=args.trials, segments=args.segments, seed=args.seed,
        stop_loss_pct=args.stop_loss, take_profit_pct=args.take_profit,
        trailing_stop_pct=args.trailing_stop, cooldown_bars=args.cooldown,
        risk_pct_per_trade=args.risk_pct, max_position_pct=args.max_position,
    )
    print(f"{args.strategy} icin {len(results)} kombinasyon denendi "
          f"({args.source}, {len(candles)} mum, {args.segments} dilim). En iyi 10:\n")
    for r in results[:10]:
        print("  " + r.row())
    print("\nPuan = dilim getirilerinin MEDYANI (tek donemin sansli kahramani elenir).")
    print("Yine de bu secim GECMISE gore yapildi - canli oncesi taze veride dogrula.")


def cmd_montecarlo(args: argparse.Namespace) -> None:
    """Backtest calistirir, sonra islemleri Monte Carlo ile sansa karsi sinar."""
    from bot.montecarlo import monte_carlo

    print(UYARI)
    candles = get_candles(args)
    strategy = build_strategy(args)
    result = run_bt(args, candles, strategy)
    print(f"Veri: {args.source}, {len(candles)} mum")
    print(result.summary())
    pnls = [t.pnl_pct for t in result.trades]
    mc = monte_carlo(pnls, trials=args.trials, ruin_pct=args.ruin_pct)
    print()
    if mc is None:
        print(f"Monte Carlo icin en az 10 islem gerekir ({len(pnls)} var).")
    else:
        print(mc.summary())


def cmd_derin(args: argparse.Namespace) -> None:
    """Tek sembol icin cok faktorlu derin analiz raporu."""
    from bot.analyst import full_report

    print(UYARI)
    fetch = smart_fetch(args.interval, args.bars)
    print(full_report(args.symbol.upper(), fetch(args.symbol.upper())))


def cmd_analyze(args: argparse.Namespace) -> None:
    """Surekli analiz modu: bot bosta dururken bile duzenli araliklarla
    tum piyasalari tarar, en iyi adaylari raporlar, Telegram'a gonderir."""
    print(UYARI)
    symbols = parse_symbols(args.symbols)
    base_fetch = smart_fetch(args.interval, args.bars)
    cache: dict[str, list[data.Candle]] = {}

    def fetch(sym: str) -> list[data.Candle]:
        if sym not in cache:
            cache[sym] = base_fetch(sym)
        return cache[sym]

    print(f"Surekli analiz: {', '.join(symbols)} ({args.interval}), "
          f"her {args.every_hours} saatte bir tur")
    print(f"Telegram: {'aktif' if telegram_configured() else 'kapali'}, "
          f"AI yorumcu: {'aktif' if ai_available() else 'kapali (OPENROUTER_API_KEY yok)'}\n")
    while True:
        cache.clear()  # her tur taze veri
        stamp = time.strftime("%Y-%m-%d %H:%M")
        lines = [f"Zenith analiz turu - {stamp} ({args.interval})"]
        try:
            results = scanner.scan(symbols, fetch)
            lines.append("En iyi 3 kombinasyon (dogrulama verisinde):")
            for r in results[:3]:
                lines.append("  " + r.row())
            pick = scanner.best_pick(results)
            if pick:
                lines.append(f"Elemeyi gecen aday: {pick.symbol} + {pick.strategy} "
                             f"(dogrulama {pick.test_return_pct:+.2f}%)")
            else:
                lines.append("Elemeyi gecen aday YOK - dogru hamle beklemek.")
            # korelasyon uyarisi: ayni yone giden enstrumanlar tek bahistir
            from bot.mathrisk import pct_returns, pearson

            cached = [s for s in symbols if s in cache]
            for i in range(len(cached)):
                for j in range(i + 1, len(cached)):
                    a, b = cached[i], cached[j]
                    corr = pearson(
                        pct_returns([c.close for c in cache[a]]),
                        pct_returns([c.close for c in cache[b]]),
                    )
                    if corr >= 0.8:
                        lines.append(
                            f"Uyari: {a} ve {b} yuksek korele ({corr:.2f}) - "
                            "ikisine birden girmek cesitlendirme degil, ayni bahsi buyutmektir."
                        )
        except Exception as e:  # noqa: BLE001 - tur atlansin ama dongu olmesin
            lines.append(f"Analiz hatasi: {e}")
        summary = "\n".join(lines)
        print(summary)
        comment = ai_comment(summary)
        if comment:
            print(f"\nAI yorumu: {comment}")
            summary += f"\n\nAI yorumu: {comment}"
        send_telegram(summary[:4000])
        if args.once:
            return
        print(f"\nSonraki tur: {args.every_hours} saat sonra. (Ctrl+C ile durdur)\n")
        time.sleep(args.every_hours * 3600)


def cmd_stats(args: argparse.Namespace) -> None:
    """Gercek islem gunlugu (trades_*.csv) performans karnesi."""
    from bot import stats

    text = stats.summary_text()
    print(text)
    if args.notify:
        send_telegram(text[:4000])
        print("\n(Telegram'a gonderildi.)")


def cmd_readiness(args: argparse.Namespace) -> None:
    """Demo/testnet gunlugunu asgari canliya gecis esiklerine karsi denetler."""
    from bot.readiness import Thresholds, evaluate, render_html

    base = os.path.dirname(os.path.abspath(__file__))
    limits = Thresholds(
        min_trades=args.min_trades,
        min_days=args.min_days,
        min_profit_factor=args.min_profit_factor,
        min_expectancy_pct=args.min_expectancy,
        max_drawdown_pct=args.max_drawdown,
        recent_trades=args.recent_trades,
    )
    report = evaluate(base, args.mode, limits)
    text = report.summary()
    print(text)
    if args.html:
        out = args.out or os.path.join(base, "report_readiness.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(render_html(report))
        print(f"\nHTML hazirlik raporu yazildi: {out}")
    if args.notify:
        send_telegram(text[:4000])
        print("\n(Telegram'a gonderildi.)")
    if args.require_pass and not report.ready:
        raise SystemExit(2)


def cmd_notify_test(args: argparse.Namespace) -> None:
    """Telegram baglantisini kurar/dogrular: chat ID bulur, test mesaji atar."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        sys.exit(
            "TELEGRAM_BOT_TOKEN yok.\n"
            "1) Telegram'da @BotFather -> /newbot ile bot olustur, token'i al\n"
            "2) trading_bot/.env dosyasina yaz: TELEGRAM_BOT_TOKEN=<token>\n"
            "3) Bu komutu tekrar calistir."
        )
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        print("TELEGRAM_CHAT_ID ayarli degil, botuna yazanlardan bulmayi deniyorum...")
        found = discover_chat_ids(token)
        if not found:
            sys.exit(
                "Sohbet bulunamadi. Telegram'da kendi botuna herhangi bir mesaj at\n"
                "(ör. 'selam'), sonra bu komutu TEKRAR calistir.\n"
                "Not: mesajlar 24 saat icinde okunmazsa Telegram listeden siler."
            )
        print("Bulunan sohbetler:")
        for cid, name in found:
            print(f"  chat_id={cid}  ({name})")
        chat_id = str(found[0][0])
        os.environ["TELEGRAM_CHAT_ID"] = chat_id
        print(f"\nIlk bulunan kullanildi: {chat_id}")
        print(f"Kalici olmasi icin trading_bot/.env dosyasina ekle: TELEGRAM_CHAT_ID={chat_id}\n")
    ok = send_telegram(
        "Zenith trading bot baglanti testi basarili! "
        "Islem acilinca/kapaninca buradan haber alacaksin."
    )
    if ok:
        print("Test mesaji GONDERILDI - telefonuna bak!")
    else:
        sys.exit("Test mesaji gonderilemedi. Token/chat_id degerlerini kontrol et.")


def main() -> None:
    load_env()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--strategy", choices=sorted(STRATEGIES), default="sma")
        sp.add_argument("--fast", type=int, default=20, help="SMA/EMA hizli periyot")
        sp.add_argument("--slow", type=int, default=50, help="SMA/EMA yavas periyot")
        sp.add_argument("--trend-filter", type=int, default=0,
                        help="Trend filtresi SMA periyodu, ör. 200 (0 = kapali)")
        sp.add_argument("--rsi-period", type=int, default=14)
        sp.add_argument("--equity", type=float, default=10_000.0, help="Baslangic sanal bakiye")
        sp.add_argument("--symbol", default="BTCUSDT")
        sp.add_argument("--interval", default="1h")
        sp.add_argument("--bars", type=int, default=1000)

    def risk_sim_flags(sp: argparse.ArgumentParser) -> None:
        """backtest/chart icin mum ici risk simulasyonu bayraklari (0 = kapali)."""
        sp.add_argument("--stop-loss", type=float, default=2.0, help="%% stop-loss simulasyonu")
        sp.add_argument("--take-profit", type=float, default=4.0, help="%% kar-al simulasyonu")
        sp.add_argument("--trailing-stop", type=float, default=0.0, help="%% iz suren stop")
        sp.add_argument("--cooldown", type=int, default=0, help="Stop sonrasi mum bekleme")
        sp.add_argument("--risk-pct", type=float, default=1.0,
                        help="Islem basina riske edilen sermaye %%")
        sp.add_argument("--max-position", type=float, default=25.0,
                        help="Tek pozisyon icin sermaye tavani %%")

    bt = sub.add_parser("backtest", help="Stratejiyi gecmis veride test et")
    common(bt)
    bt.add_argument("--source", choices=["synthetic", "csv", "binance", "yahoo"], default="synthetic")
    bt.add_argument("--csv", help="CSV dosya yolu (--source csv icin)")
    bt.add_argument("--seed", type=int, default=42)
    bt.add_argument("--commission", type=float, default=0.1, help="Islem basina %% komisyon")
    bt.add_argument("--slippage", type=float, default=0.05, help="Islem basina %% kayma")
    risk_sim_flags(bt)

    pt = sub.add_parser("paper", help="Sanal parayla canli sinyal takibi (emir gondermez)")
    common(pt)

    sc = sub.add_parser("scan", help="Otomatik arastirma: sembol x strateji x parametre tarama")
    sc.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    sc.add_argument("--interval", default="4h")
    sc.add_argument("--bars", type=int, default=1000)
    sc.add_argument("--source", choices=["binance", "synthetic"], default="binance")
    risk_sim_flags(sc)

    tr = sub.add_parser("trade", help="Otomatik islem dongusu (paper/testnet/live)")
    common(tr)
    tr.add_argument("--symbols", default="", help="Coklu sembol: BTCUSDT,ETHUSDT,SOLUSDT")
    tr.add_argument("--mode", choices=["paper", "testnet", "live"], default="paper")
    tr.add_argument("--risk-pct", type=float, default=1.0, help="Islem basina %% risk")
    tr.add_argument("--stop-loss", type=float, default=2.0, help="%% stop-loss")
    tr.add_argument("--take-profit", type=float, default=4.0, help="%% kar al")
    tr.add_argument("--max-daily-loss", type=float, default=5.0, help="Gunluk %% zarar freni")
    tr.add_argument("--trailing-stop", type=float, default=0.0,
                    help="Iz suren stop %% (tepe fiyattan geri cekilme; 0 = kapali)")
    tr.add_argument("--atr-stop", type=float, default=0.0,
                    help="ATR stop katsayisi, ör. 2.0 (0 = kapali; aciksa sabit stop yerine gecer)")
    tr.add_argument("--cooldown", type=int, default=3,
                    help="Stop sonrasi kac mum yeni giris yok (0 = kapali)")
    tr.add_argument("--stoploss-guard", type=int, default=3,
                    help="Ayni gun bu kadar stop yenirse gunu kapat (0 = kapali)")
    tr.add_argument("--riski-anladim", action="store_true",
                    help="live mod onayi: gercek para kaybedebilecegimi anladim")
    tr.add_argument("--news-filter", action=argparse.BooleanOptionalAction, default=True,
                    help="Buyuk haber saatlerinde yeni giris yapma (kapatmak: --no-news-filter)")
    tr.add_argument("--daily-trend", action=argparse.BooleanOptionalAction, default=True,
                    help="Gunluk SMA200 altindayken long acma (kapatmak: --no-daily-trend)")
    tr.add_argument("--poll-seconds", type=int, default=60,
                    help="Stop/risk kontrol araligi saniye (5-300)")

    wf = sub.add_parser("walkforward", help="Stratejiyi ardisik zaman dilimlerinde dogrula")
    common(wf)
    wf.add_argument("--source", choices=["synthetic", "csv", "binance", "yahoo"], default="binance")
    wf.add_argument("--csv", help="CSV dosya yolu (--source csv icin)")
    wf.add_argument("--seed", type=int, default=42)
    wf.add_argument("--segments", type=int, default=5, help="Dilim sayisi")
    risk_sim_flags(wf)

    ch = sub.add_parser("chart", help="Backtest + equity egrisi grafikli HTML rapor")
    common(ch)
    ch.add_argument("--source", choices=["synthetic", "csv", "binance", "yahoo"], default="binance")
    ch.add_argument("--csv", help="CSV dosya yolu (--source csv icin)")
    ch.add_argument("--seed", type=int, default=42)
    ch.add_argument("--commission", type=float, default=0.1)
    ch.add_argument("--slippage", type=float, default=0.05)
    ch.add_argument("--out", help="Cikti dosyasi (varsayilan: report_SEMBOL_strateji.html)")
    risk_sim_flags(ch)

    op = sub.add_parser("optimize", help="Parametre optimizasyonu (walk-forward puanlamali)")
    common(op)
    op.add_argument("--source", choices=["synthetic", "csv", "binance", "yahoo"], default="binance")
    op.add_argument("--csv", help="CSV dosya yolu (--source csv icin)")
    op.add_argument("--seed", type=int, default=42)
    op.add_argument("--trials", type=int, default=30, help="Denenecek kombinasyon sayisi")
    op.add_argument("--segments", type=int, default=5, help="Walk-forward dilim sayisi")
    risk_sim_flags(op)

    an = sub.add_parser("analyze", help="Surekli analiz: bosta bile tarar, Telegram'a rapor atar")
    an.add_argument("--symbols", default="BTCUSDT,ETHUSDT,EURUSD,XAUUSD",
                    help="Karisik liste: USDT ile bitenler Binance, digerleri Yahoo (forex/altin)")
    an.add_argument("--interval", default="1d", help="Mum periyodu (yahoo: 1h veya 1d onerilir)")
    an.add_argument("--bars", type=int, default=1000)
    an.add_argument("--every-hours", type=float, default=6.0, help="Tur araligi (saat)")
    an.add_argument("--once", action="store_true", help="Tek tur calis ve cik")

    rp = sub.add_parser("report", help="Sanal portfoy durum raporu")
    rp.add_argument("--html", action="store_true", help="Portfoy tarihcesi HTML grafigi uret")

    st = sub.add_parser("stats", help="Gercek islem karnesi (trades_*.csv analizi)")
    st.add_argument("--notify", action="store_true", help="Ozeti Telegram'a da gonder")
    rd = sub.add_parser("readiness", help="Demo/testnet verisinden canliya hazirlik kapisi")
    rd.add_argument("--mode", choices=["validation", "paper", "testnet", "demo", "live", "all"],
                    default="validation", help="Dahil edilecek islem modu")
    rd.add_argument("--min-trades", type=int, default=100)
    rd.add_argument("--min-days", type=int, default=60)
    rd.add_argument("--min-profit-factor", type=float, default=1.20)
    rd.add_argument("--min-expectancy", type=float, default=0.0)
    rd.add_argument("--max-drawdown", type=float, default=10.0)
    rd.add_argument("--recent-trades", type=int, default=30)
    rd.add_argument("--html", action="store_true", help="Equity/drawdown HTML grafigi uret")
    rd.add_argument("--out", help="HTML cikti yolu")
    rd.add_argument("--notify", action="store_true", help="Ozeti Telegram'a da gonder")
    rd.add_argument("--require-pass", action="store_true",
                    help="Kapidan kalirsa otomasyon icin cikis kodu 2 dondur")
    sub.add_parser("notify-test", help="Telegram baglantisini kur ve test mesaji at")
    mc = sub.add_parser("montecarlo", help="Backtest + Monte Carlo: sonuc ne kadar sansa bagliydi?")
    common(mc)
    mc.add_argument("--source", choices=["synthetic", "csv", "binance", "yahoo"], default="binance")
    mc.add_argument("--csv", help="CSV dosya yolu (--source csv icin)")
    mc.add_argument("--seed", type=int, default=42)
    mc.add_argument("--commission", type=float, default=0.1)
    mc.add_argument("--slippage", type=float, default=0.05)
    mc.add_argument("--trials", type=int, default=2000, help="Simulasyon sayisi")
    mc.add_argument("--ruin-pct", type=float, default=50.0, help="Iflas esigi (%% kayip)")
    risk_sim_flags(mc)

    dr = sub.add_parser("derin", help="Tek sembol derin analiz: rejim, trend, momentum, seviyeler")
    dr.add_argument("--symbol", default="XAUUSD")
    dr.add_argument("--interval", default="1d")
    dr.add_argument("--bars", type=int, default=1000)

    sub.add_parser("telegram", help="Telegram komut servisi: /durum /fiyat /analiz /rapor /derin")

    args = p.parse_args()
    if args.cmd == "backtest":
        cmd_backtest(args)
    elif args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "trade":
        cmd_trade(args)
    elif args.cmd == "walkforward":
        cmd_walkforward(args)
    elif args.cmd == "analyze":
        cmd_analyze(args)
    elif args.cmd == "chart":
        cmd_chart(args)
    elif args.cmd == "optimize":
        cmd_optimize(args)
    elif args.cmd == "report":
        cmd_report(args)
    elif args.cmd == "stats":
        cmd_stats(args)
    elif args.cmd == "readiness":
        cmd_readiness(args)
    elif args.cmd == "notify-test":
        cmd_notify_test(args)
    elif args.cmd == "montecarlo":
        cmd_montecarlo(args)
    elif args.cmd == "derin":
        cmd_derin(args)
    elif args.cmd == "telegram":
        from bot.telegram_bot import TelegramCommander

        print(UYARI)
        TelegramCommander().run_forever()
    else:
        cmd_paper(args)


if __name__ == "__main__":
    main()
