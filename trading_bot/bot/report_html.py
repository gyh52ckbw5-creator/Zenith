"""Backtest sonucundan tek dosyalik HTML rapor uretir (equity egrisi SVG).

Harici kutuphane yok: grafik saf SVG olarak cizilir, dosyayi tarayicida
acman yeterli. Mavi cizgi strateji, gri cizgi al-ve-tut kiyasi.
"""

from __future__ import annotations

from .backtest import Result
from .data import Candle

_W, _H, _PAD = 900, 360, 46


def _polyline(values: list[float], lo: float, hi: float, color: str, width: int = 2) -> str:
    if hi <= lo:
        hi = lo + 1e-9
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = _PAD + (_W - 2 * _PAD) * (i / max(1, n - 1))
        y = _H - _PAD - (_H - 2 * _PAD) * ((v - lo) / (hi - lo))
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<polyline fill="none" stroke="{color}" stroke-width="{width}" '
        f'points="{" ".join(pts)}"/>'
    )


def render_html(result: Result, candles: list[Candle], title: str) -> str:
    equity = result.equity_curve
    # al-ve-tut kiyas egrisi: ayni baslangic sermayesiyle ilk mumda al, tut
    base = candles[1].open if len(candles) > 1 else candles[0].close
    bh = [result.start_equity * c.close / base for c in candles]
    lo = min(min(equity), min(bh))
    hi = max(max(equity), max(bh))

    grid = []
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = _H - _PAD - (_H - 2 * _PAD) * frac
        val = lo + (hi - lo) * frac
        grid.append(
            f'<line x1="{_PAD}" y1="{y:.1f}" x2="{_W - _PAD}" y2="{y:.1f}" '
            f'stroke="#ccc" stroke-dasharray="4 4"/>'
            f'<text x="6" y="{y + 4:.1f}" font-size="11" fill="#666">{val:,.0f}</text>'
        )

    rows = "".join(
        f"<tr><td>{k}</td><td style='text-align:right'>{v}</td></tr>"
        for k, v in [
            ("Toplam getiri", f"{result.total_return_pct:+.2f}%"),
            ("Al-ve-tut getirisi (kiyas)", f"{result.buy_hold_return_pct:+.2f}%"),
            ("Maksimum dusus", f"{result.max_drawdown_pct:.2f}%"),
            ("Islem sayisi", result.n_trades),
            ("Kazanma orani", f"{result.win_rate_pct:.1f}%"),
            ("Kar faktoru", f"{result.profit_factor:.2f}"),
            ("Sharpe (kaba)", f"{result.sharpe:.2f}"),
        ]
    )

    trade_rows = "".join(
        f"<tr><td>{i}</td><td>{t.entry_price:,.4f}</td><td>{t.exit_price:,.4f}</td>"
        f"<td style='text-align:right;color:{'#0a7d38' if t.pnl_pct > 0 else '#c0392b'}'>"
        f"{t.pnl_pct:+.2f}%</td></tr>"
        for i, t in enumerate(result.trades, 1)
    )

    return f"""<!-- Zenith trading bot raporu -->
<meta charset="utf-8">
<title>{title}</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 12px;color:#222}}
 table{{border-collapse:collapse;margin:12px 0}} td,th{{border:1px solid #ddd;padding:6px 12px}}
 .uyari{{background:#fff3cd;border:1px solid #ffec99;padding:10px 14px;border-radius:6px}}
</style>
<h1>{title}</h1>
<p class="uyari"><b>Uyari:</b> Egitim amacli rapor. Gecmis performans gelecegi
garanti etmez; bu bir yatirim tavsiyesi degildir.</p>
<h2>Equity egrisi</h2>
<svg viewBox="0 0 {_W} {_H}" style="width:100%;background:#fafafa;border:1px solid #eee">
{"".join(grid)}
{_polyline(bh, lo, hi, "#999")}
{_polyline(equity, lo, hi, "#1668c7", 3)}
<text x="{_PAD}" y="20" font-size="13" fill="#1668c7">■ {result.strategy}</text>
<text x="{_PAD + 220}" y="20" font-size="13" fill="#777">■ al-ve-tut</text>
</svg>
<h2>Ozet</h2>
<table>{rows}</table>
<h2>Islemler ({result.n_trades})</h2>
<table><tr><th>#</th><th>Giris</th><th>Cikis</th><th>K/Z</th></tr>{trade_rows}</table>
"""
