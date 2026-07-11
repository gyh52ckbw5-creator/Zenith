"""Derin analiz motoru: bir profesyonel analistin bakis acisiyla rapor.

Tek sembol icin cok faktorlu okuma yapar:
  1. Piyasa rejimi (ADX): trend mi, yatay mi?
  2. Trend konumu: fiyat vs SMA50/SMA200, altin/olum kesisimi durumu
  3. Momentum: RSI + MACD uyumu
  4. Oynaklik: ATR'nin tarihsel yuzdeligi (sakin mi, firtina mi?)
  5. Seviyeler: destek/direnc (100 mum), Donchian kirilim mesafeleri
  6. Getiri tablosu: 5 ve 30 mumluk degisim
  7. Strateji kosesi: 13 kombinasyonluk hizli tarama + dogrulama sonucu
  8. Faktor oylamasi ile GENEL EGILIM - ve durustluk notu

Hicbir faktor tek basina karar degildir; rapor 'kesin al/sat' demez,
tablonun tamamini gosterir. Dunyanin en iyi analisti de gelecegi bilmez -
farki, ne bilmedigini bilmesidir.
"""

from __future__ import annotations

from .data import Candle
from .indicators import adx, atr, macd, rsi, sma
from .scanner import best_pick, scan

DISCLAIMER = "Egitim amaclidir; yatirim tavsiyesi degildir. Gecmis, gelecegi garanti etmez."


def _pct(a: float, b: float) -> float:
    return 100.0 * (a / b - 1) if b else 0.0


def full_report(symbol: str, candles: list[Candle]) -> str:
    if len(candles) < 260:
        return f"{symbol}: derin analiz icin en az 260 mum gerekir ({len(candles)} var)."

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    last = closes[-1]

    up_votes: list[str] = []
    down_votes: list[str] = []
    lines: list[str] = [f"DERIN ANALIZ - {symbol} (son fiyat {last:,.4f})", ""]

    # 1. Rejim (ADX)
    adx_series = adx(highs, lows, closes, 14)
    adx_val = next((v for v in reversed(adx_series) if v is not None), None)
    if adx_val is None:
        regime = "hesaplanamadi"
    elif adx_val >= 25:
        regime = f"GUCLU TREND (ADX {adx_val:.0f}) - trend takip stratejilerinin havasi"
    elif adx_val >= 20:
        regime = f"zayif trend (ADX {adx_val:.0f}) - kararsiz bolge"
    else:
        regime = f"YATAY piyasa (ADX {adx_val:.0f}) - kirilim sinyalleri testere yapabilir"
    lines.append(f"1) Rejim: {regime}")

    # 2. Trend konumu
    sma50 = sma(closes, 50)[-1]
    sma200 = sma(closes, 200)[-1]
    pos50 = _pct(last, sma50)
    pos200 = _pct(last, sma200)
    cross = "altin kesisim bolgesi (SMA50 > SMA200)" if sma50 > sma200 else "olum kesisimi bolgesi (SMA50 < SMA200)"
    lines.append(
        f"2) Trend: fiyat SMA50'nin {pos50:+.1f}%, SMA200'un {pos200:+.1f}% "
        f"{'ustunde' if pos200 >= 0 else 'altinda'}; {cross}"
    )
    (up_votes if pos200 >= 0 else down_votes).append("SMA200")
    (up_votes if pos50 >= 0 else down_votes).append("SMA50")
    (up_votes if sma50 > sma200 else down_votes).append("kesisim")

    # 3. Momentum
    rsi_val = rsi(closes, 14)[-1]
    line_m, sig_m = macd(closes)
    macd_up = line_m[-1] is not None and sig_m[-1] is not None and line_m[-1] > sig_m[-1]
    rsi_note = "notr"
    if rsi_val is not None:
        if rsi_val >= 70:
            rsi_note = "ASIRI ALIM (geri cekilme riski)"
        elif rsi_val <= 30:
            rsi_note = "ASIRI SATIM (tepki potansiyeli)"
    lines.append(
        f"3) Momentum: RSI {rsi_val:.0f} ({rsi_note}); "
        f"MACD sinyalin {'USTUNDE - yukari momentum' if macd_up else 'ALTINDA - asagi momentum'}"
    )
    (up_votes if macd_up else down_votes).append("MACD")

    # 4. Oynaklik yuzdeligi
    atr_series = [v for v in atr(highs, lows, closes, 14) if v is not None]
    cur_atr = atr_series[-1]
    percentile = 100.0 * sum(1 for v in atr_series if v <= cur_atr) / len(atr_series)
    vol_note = "FIRTINA - stoplari genis tut" if percentile >= 80 else (
        "sakin - kirilim oncesi sikisma olabilir" if percentile <= 20 else "normal"
    )
    lines.append(
        f"4) Oynaklik: ATR {cur_atr:,.4f}, tarihsel yuzdelik %{percentile:.0f} ({vol_note})"
    )

    # 5. Seviyeler
    res100 = max(highs[-101:-1])
    sup100 = min(lows[-101:-1])
    hi55 = max(highs[-56:-1])
    lo20 = min(lows[-21:-1])
    lines.append(
        f"5) Seviyeler: direnc {res100:,.4f} ({_pct(res100, last):+.1f}%), "
        f"destek {sup100:,.4f} ({_pct(sup100, last):+.1f}%); "
        f"Donchian: 55-mum kirilimina {_pct(hi55, last):+.1f}%, 20-mum dibine {_pct(lo20, last):+.1f}%"
    )

    # 6. Getiriler
    r5 = _pct(last, closes[-6])
    r30 = _pct(last, closes[-31])
    lines.append(f"6) Getiri: son 5 mum {r5:+.2f}%, son 30 mum {r30:+.2f}%")
    (up_votes if r30 >= 0 else down_votes).append("30-mum getiri")

    # 7. Strateji kosesi (ayni veriyle hizli tarama)
    results = scan([symbol], lambda _s: candles)
    pick = best_pick(results)
    if pick:
        lines.append(
            f"7) Strateji: elemeyi gecen aday {pick.strategy} "
            f"(dogrulama {pick.test_return_pct:+.1f}%, al-tut {pick.test_buy_hold_pct:+.1f}%)"
        )
    else:
        lines.append("7) Strateji: 13 kombinasyondan elemeyi gecen YOK - beklemek de pozisyondur")

    # 8. Genel egilim oylamasi
    total = len(up_votes) + len(down_votes)
    if len(up_votes) >= total - 1:
        bias = "YUKARI egilim"
    elif len(down_votes) >= total - 1:
        bias = "ASAGI egilim"
    else:
        bias = "KARISIK tablo"
    lines.append("")
    lines.append(
        f"GENEL: {bias} ({len(up_votes)}/{total} faktor yukari: "
        f"{', '.join(up_votes) or '-'} | asagi: {', '.join(down_votes) or '-'})"
    )
    if adx_val is not None and adx_val < 20:
        lines.append("Not: ADX yatay diyor - egilim oylari yatayda guvenilmez, teyit bekle.")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
