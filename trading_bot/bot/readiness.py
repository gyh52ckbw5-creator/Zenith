"""Demo/testnet islem gunlugunden canliya hazirlik kapisi ve HTML raporu."""

from __future__ import annotations

import csv
import glob
import html
import math
import os
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trade:
    timestamp: datetime
    mode: str
    symbol: str
    pnl_pct: float


@dataclass(frozen=True)
class Thresholds:
    min_trades: int = 100
    min_days: int = 60
    min_profit_factor: float = 1.20
    min_expectancy_pct: float = 0.0
    max_drawdown_pct: float = 10.0
    recent_trades: int = 30

    def validate(self) -> None:
        if self.min_trades <= 0 or self.min_days <= 0 or self.recent_trades <= 0:
            raise ValueError("islem/gun/yakin donem esikleri pozitif olmali")
        if self.min_profit_factor <= 0 or self.max_drawdown_pct <= 0:
            raise ValueError("kar faktoru ve drawdown esikleri pozitif olmali")


@dataclass
class Readiness:
    trades: list[Trade]
    thresholds: Thresholds
    invalid_rows: int = 0

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def days(self) -> int:
        if not self.trades:
            return 0
        return (self.trades[-1].timestamp.date() - self.trades[0].timestamp.date()).days + 1

    @property
    def expectancy_pct(self) -> float:
        return sum(t.pnl_pct for t in self.trades) / self.n if self.n else 0.0

    @property
    def profit_factor(self) -> float:
        wins = sum(t.pnl_pct for t in self.trades if t.pnl_pct > 0)
        losses = -sum(t.pnl_pct for t in self.trades if t.pnl_pct < 0)
        return (wins / losses) if losses else (math.inf if wins else 0.0)

    @property
    def equity_curve(self) -> list[float]:
        curve = [100.0]
        for trade in self.trades:
            curve.append(max(0.0, curve[-1] * (1.0 + trade.pnl_pct / 100.0)))
        return curve

    @property
    def max_drawdown_pct(self) -> float:
        peak = 0.0
        worst = 0.0
        for value in self.equity_curve:
            peak = max(peak, value)
            if peak > 0:
                worst = max(worst, 100.0 * (peak - value) / peak)
        return worst

    @property
    def recent_expectancy_pct(self) -> float:
        recent = self.trades[-self.thresholds.recent_trades :]
        return sum(t.pnl_pct for t in recent) / len(recent) if recent else 0.0

    @property
    def checks(self) -> list[tuple[str, bool, str]]:
        t = self.thresholds
        pf = self.profit_factor
        return [
            ("Ornek sayisi", self.n >= t.min_trades, f"{self.n}/{t.min_trades} islem"),
            ("Takvim suresi", self.days >= t.min_days, f"{self.days}/{t.min_days} gun"),
            (
                "Kar faktoru",
                pf >= t.min_profit_factor,
                f"{'inf' if math.isinf(pf) else f'{pf:.2f}'}/{t.min_profit_factor:.2f}",
            ),
            (
                "Beklenti",
                self.expectancy_pct > t.min_expectancy_pct,
                f"{self.expectancy_pct:+.3f}% (esik > {t.min_expectancy_pct:+.3f}%)",
            ),
            (
                "Maksimum dusus",
                self.max_drawdown_pct <= t.max_drawdown_pct,
                f"{self.max_drawdown_pct:.2f}%/{t.max_drawdown_pct:.2f}%",
            ),
            (
                "Yakin donem",
                self.n >= t.recent_trades and self.recent_expectancy_pct > 0,
                f"son {min(self.n, t.recent_trades)} beklenti {self.recent_expectancy_pct:+.3f}%",
            ),
            ("Veri kalitesi", self.invalid_rows == 0, f"{self.invalid_rows} bozuk satir"),
        ]

    @property
    def ready(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def summary(self) -> str:
        title = "CANLIYA HAZIRLIK: GECTI" if self.ready else "CANLIYA HAZIRLIK: KALDI"
        lines = [title]
        for name, ok, detail in self.checks:
            lines.append(f"  {'OK' if ok else 'FAIL':<4} {name:<18} {detail}")
        lines.extend(
            [
                "",
                "Bu kapinin gecmesi kar garantisi degildir; yalnizca asgari veri/risk",
                "disiplininin saglandigini gosterir. Once preflight ve cok kucuk tutar.",
            ]
        )
        return "\n".join(lines)


def _parse_time(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            pass
    raise ValueError(f"gecersiz zaman: {value}")


def load_trades(base_dir: str, mode: str = "validation") -> tuple[list[Trade], int]:
    """Alt klasorler dahil standart trades_*.csv gunluklerini okur."""
    allowed = {
        "validation": {"paper", "testnet", "demo"},
        "paper": {"paper"},
        "testnet": {"testnet"},
        "demo": {"demo"},
        "live": {"live"},
        "all": None,
    }
    if mode not in allowed:
        raise ValueError(f"gecersiz mode: {mode}")
    records: list[Trade] = []
    invalid = 0
    pattern = os.path.join(base_dir, "**", "trades_*.csv")
    for path in sorted(glob.glob(pattern, recursive=True)):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    row_mode = (row.get("mod") or "").strip().lower()
                    if allowed[mode] is not None and row_mode not in allowed[mode]:
                        continue
                    # Kaldiracli/parsiyel pozisyonda fiyat getirisi hesap
                    # getirisi degildir. Eski sema fail-closed reddedilir.
                    pnl = float(row["hesap_kz_yuzde"])
                    if not math.isfinite(pnl) or pnl <= -100:
                        raise ValueError("gecersiz pnl")
                    records.append(
                        Trade(
                            timestamp=_parse_time(row["zaman"]),
                            mode=row_mode,
                            symbol=(row.get("sembol") or "?").strip(),
                            pnl_pct=pnl,
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    invalid += 1
    records.sort(key=lambda x: x.timestamp)
    return records, invalid


def evaluate(base_dir: str, mode: str = "validation",
             thresholds: Thresholds | None = None) -> Readiness:
    limits = thresholds or Thresholds()
    limits.validate()
    trades, invalid = load_trades(base_dir, mode)
    return Readiness(trades=trades, thresholds=limits, invalid_rows=invalid)


def _points(values: list[float], width: int, height: int) -> str:
    if not values:
        return ""
    low, high = min(values), max(values)
    span = max(high - low, 1e-9)
    denom = max(len(values) - 1, 1)
    return " ".join(
        f"{i * width / denom:.1f},{height - (v - low) * height / span:.1f}"
        for i, v in enumerate(values)
    )


def render_html(report: Readiness, title: str = "Zenith canliya hazirlik") -> str:
    curve = report.equity_curve
    peak = curve[0] if curve else 100.0
    drawdowns = []
    for value in curve:
        peak = max(peak, value)
        drawdowns.append(100.0 * (peak - value) / peak if peak else 0.0)
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td class=\"{'ok' if ok else 'fail'}\">"
        f"{'GECTI' if ok else 'KALDI'}</td><td>{html.escape(detail)}</td></tr>"
        for name, ok, detail in report.checks
    )
    return f"""<!doctype html>
<html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title>
<style>
body{{font:15px system-ui;background:#0b1020;color:#e8eefc;max-width:1000px;margin:auto;padding:24px}}
.card{{background:#151d33;border:1px solid #2a3658;border-radius:14px;padding:18px;margin:16px 0}}
h1{{color:{'#69db7c' if report.ready else '#ff6b6b'}}} table{{width:100%;border-collapse:collapse}}
td{{padding:9px;border-bottom:1px solid #2a3658}}.ok{{color:#69db7c}}.fail{{color:#ff6b6b}}
svg{{width:100%;height:260px;background:#0e1529;border-radius:10px}}small{{color:#9aa8c7}}
</style><h1>{html.escape(title)} — {'GECTI' if report.ready else 'KALDI'}</h1>
<div class="card"><table>{rows}</table></div>
<div class="card"><h2>Bilesik islem getirisi (100 baz)</h2>
<svg viewBox="0 0 900 220"><polyline fill="none" stroke="#4dabf7" stroke-width="3"
points="{_points(curve, 900, 220)}"/></svg></div>
<div class="card"><h2>Drawdown</h2>
<svg viewBox="0 0 900 220"><polyline fill="none" stroke="#ff6b6b" stroke-width="3"
points="{_points(drawdowns, 900, 220)}"/></svg></div>
<small>Hesap bazli yuzdesel sonuclar sirayla bilesik uygulanmistir. Eski,
yalnizca fiyat getirisi iceren gunlukler fail-closed reddedilir. Kar faktoru
hesap getirilerinden yaklasik hesaplanir. Gecmis performans gelecegi garanti etmez.</small></html>"""
