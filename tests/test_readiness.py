import csv
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot.readiness import Thresholds, evaluate, load_trades, render_html  # noqa: E402


def _write(path, pnls, *, mode="demo", start=datetime(2026, 1, 1)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "zaman", "mod", "sembol", "giris", "cikis",
            "kz_yuzde", "hesap_kz_yuzde", "neden",
        ])
        for i, pnl in enumerate(pnls):
            w.writerow([
                (start + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S"),
                mode, "EURUSD", 1.0, 1.0, pnl, pnl, "test",
            ])


def test_readiness_passes_robust_track_record(tmp_path):
    _write(tmp_path / "mt5" / "trades_mt5_EURUSD.csv", [2.0, -1.0] * 50 + [1.0] * 30)
    limits = Thresholds(min_trades=100, min_days=60, recent_trades=30)
    report = evaluate(str(tmp_path), thresholds=limits)
    assert report.ready is True
    assert report.n == 130
    assert report.days == 130
    assert report.profit_factor > 1.2
    assert report.recent_expectancy_pct > 0


def test_readiness_fails_short_or_deteriorating_record(tmp_path):
    _write(tmp_path / "trades_BTCUSDT.csv", [2.0] * 20 + [-3.0] * 10, mode="paper")
    report = evaluate(
        str(tmp_path),
        thresholds=Thresholds(min_trades=30, min_days=20, recent_trades=10),
    )
    assert report.ready is False
    assert report.recent_expectancy_pct == -3.0
    assert report.max_drawdown_pct > 10


def test_mode_filter_invalid_rows_and_html(tmp_path):
    _write(tmp_path / "trades_A.csv", [1.0, -0.5], mode="demo")
    _write(tmp_path / "trades_B.csv", [50.0], mode="live")
    with (tmp_path / "trades_A.csv").open("a", encoding="utf-8") as f:
        f.write("bozuk,demo,A,1,2,nan,nan,test\n")
    trades, invalid = load_trades(str(tmp_path), "validation")
    assert len(trades) == 2
    assert invalid == 1
    report = evaluate(
        str(tmp_path),
        thresholds=Thresholds(min_trades=2, min_days=2, recent_trades=2),
    )
    html = render_html(report)
    assert "Bilesik islem getirisi" in html
    assert "<svg" in html
    assert "KALDI" in html  # bozuk satir veri kalitesi kapisini kapatir
