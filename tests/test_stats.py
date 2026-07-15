"""Islem karnesi (stats) testleri."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading_bot"))

from bot import stats  # noqa: E402


def _write(tmp_path, name, rows):
    p = tmp_path / name
    lines = ["zaman,mod,sembol,giris,cikis,kz_yuzde,neden"]
    for pnl, reason in rows:
        lines.append(f"2026-01-01,paper,X,100,101,{pnl},{reason}")
    p.write_text("\n".join(lines) + "\n")
    return p


def test_analyze_csv_metrics(tmp_path):
    p = _write(tmp_path, "trades_BTCUSDT.csv",
               [(6.0, "take_profit"), (-2.0, "stop_loss"), (-1.0, "stop_loss")])
    s = stats.analyze_csv(str(p))
    assert s.n == 3 and s.wins == 1 and s.losses == 2
    assert abs(s.win_rate - 33.333) < 0.01
    assert abs(s.expectancy - 1.0) < 1e-9        # (6-2-1)/3
    assert abs(s.profit_factor - 2.0) < 1e-9     # 6 / 3
    assert s.best == 6.0 and s.worst == -2.0
    assert s.by_reason == {"take_profit": 1, "stop_loss": 2}


def test_summary_empty(tmp_path):
    assert "Henuz kapanmis islem yok" in stats.summary_text(str(tmp_path))


def test_summary_positive_and_negative(tmp_path):
    _write(tmp_path, "trades_AAA.csv", [(5.0, "take_profit"), (3.0, "take_profit")])
    out = stats.summary_text(str(tmp_path))
    assert "KAZANDIRMIS" in out and "TOPLAM" in out

    for f in tmp_path.glob("trades_*.csv"):
        f.unlink()
    _write(tmp_path, "trades_BBB.csv", [(-5.0, "stop_loss"), (1.0, "take_profit")])
    out2 = stats.summary_text(str(tmp_path))
    assert "KAZANDIRMAMIS" in out2


def test_agent_has_karne_tool():
    from zenith.agent import TOOLS
    assert "karne" in TOOLS
