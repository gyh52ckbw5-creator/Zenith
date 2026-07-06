"""Risk yonetimi: pozisyon boyutlandirma, stop-loss/take-profit, gunluk
zarar freni (kill switch).

Profesyonel ile kumarbazi ayiran katman budur. "Cok para lazim" diye
pozisyonu buyutmek, hesabin sifirlanma olasiligini buyutur:
%50 kaybeden hesabin basa donmesi icin %100 kazanmasi gerekir.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskConfig:
    risk_pct_per_trade: float = 1.0   # islem basina riske edilen sermaye yuzdesi
    stop_loss_pct: float = 2.0        # giristen bu kadar dusunce kes
    take_profit_pct: float = 4.0      # giristen bu kadar yukselince al (2:1 odul/risk)
    max_position_pct: float = 25.0    # tek pozisyon sermayenin en fazla bu kadari
    max_daily_loss_pct: float = 5.0   # gun ici toplam zarar bunu asarsa DUR
    trailing_stop_pct: float = 0.0    # tepe fiyattan bu kadar dusunce kes (0 = kapali)

    def validate(self) -> None:
        if not (0 < self.risk_pct_per_trade <= 5):
            raise ValueError("risk_pct_per_trade 0-5 araliginda olmali (5 bile agresif)")
        if self.stop_loss_pct <= 0 or self.take_profit_pct <= 0:
            raise ValueError("stop_loss_pct ve take_profit_pct pozitif olmali")
        if self.max_position_pct > 100:
            raise ValueError("max_position_pct 100'u asamaz")


def position_size_quote(equity: float, cfg: RiskConfig) -> float:
    """Pozisyona ayrilacak tutari (quote para, ör. USDT) hesaplar.

    Mantik: stop-loss yerse kaybedilecek tutar = sermaye * risk_pct olsun.
    pozisyon * stop_loss_pct = sermaye * risk_pct  =>  pozisyon = ...
    Ustten max_position_pct ile sinirlanir.
    """
    cfg.validate()
    if equity <= 0:
        return 0.0
    by_risk = equity * (cfg.risk_pct_per_trade / 100.0) / (cfg.stop_loss_pct / 100.0)
    cap = equity * (cfg.max_position_pct / 100.0)
    return round(min(by_risk, cap), 2)


def exit_reason(entry_price: float, price: float, cfg: RiskConfig) -> str | None:
    """Stop-loss / take-profit tetiklendi mi? None ise pozisyon devam."""
    change_pct = 100.0 * (price / entry_price - 1)
    if change_pct <= -cfg.stop_loss_pct:
        return "stop_loss"
    if change_pct >= cfg.take_profit_pct:
        return "take_profit"
    return None


def trailing_exit(peak_price: float, price: float, cfg: RiskConfig) -> bool:
    """Iz suren stop: pozisyondayken gorulen tepe fiyattan trailing_stop_pct
    kadar geri cekilme olursa True. Kar kilitlemenin klasik yolu."""
    if cfg.trailing_stop_pct <= 0 or peak_price <= 0:
        return False
    return price <= peak_price * (1 - cfg.trailing_stop_pct / 100.0)


def daily_kill_switch(day_start_equity: float, equity: float, cfg: RiskConfig) -> bool:
    """Gunluk zarar limiti asildiysa True: bugun islem YOK, yarin devam."""
    if day_start_equity <= 0:
        return False
    loss_pct = 100.0 * (1 - equity / day_start_equity)
    return loss_pct >= cfg.max_daily_loss_pct
