#!/usr/bin/env bash
# Sunucuda tek komutla kurulum: .env kontrolu, baglanti testi ve
# systemd servisleri (zenith-trader + zenith-analyze).
# Kullanim: cd Zenith/trading_bot && ./kur.sh
set -euo pipefail
cd "$(dirname "$0")"
BOT_DIR="$(pwd)"
PY="$(command -v python3)"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "HATA: .env yeni olusturuldu ama bos."
    echo "Once doldur:  nano $BOT_DIR/.env   (TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID)"
    echo "Sonra tekrar calistir: ./kur.sh"
    exit 1
fi

echo "-> Telegram baglantisi test ediliyor..."
"$PY" run.py notify-test

if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
    echo "UYARI: systemd calismiyor (Codespaces/konteyner olabilir). Servis kurulamaz."
    echo "El ile calistirma: $PY run.py trade --mode paper --symbols BTCUSDT,ETHUSDT"
    exit 1
fi

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "-> systemd servisleri kuruluyor..."
$SUDO tee /etc/systemd/system/zenith-trader.service >/dev/null <<EOF
[Unit]
Description=Zenith trading bot (paper islemci)
After=network-online.target

[Service]
WorkingDirectory=$BOT_DIR
ExecStart=$PY run.py trade --mode paper --symbols BTCUSDT,ETHUSDT --strategy sma
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

$SUDO tee /etc/systemd/system/zenith-analyze.service >/dev/null <<EOF
[Unit]
Description=Zenith surekli piyasa analizi
After=network-online.target

[Service]
WorkingDirectory=$BOT_DIR
ExecStart=$PY run.py analyze --symbols BTCUSDT,ETHUSDT,EURUSD,XAUUSD --interval 1d --every-hours 6
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now zenith-trader zenith-analyze

echo ""
echo "Kurulum tamam! Kontrol komutlari:"
echo "  systemctl status zenith-trader zenith-analyze"
echo "  journalctl -u zenith-trader -f"
echo "Bot islem actiginda/kapattiginda Telegram'dan haber alacaksin."
