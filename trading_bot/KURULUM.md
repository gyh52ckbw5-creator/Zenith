# KURULUM PLANI — Sıfırdan Çalışan Sisteme (iPhone kullanıcısı için)

> Sıralı ilerle; bir fazı bitirmeden diğerine geçme. Her fazın sonunda
> "kontrol" maddesi var — o sağlanmadan ilerleme.

## FAZ 0 — Bugün, sadece iPhone ile (≈30 dk, bedava)

1. **Telegram token'ını yenile** (ekran görüntüsünde açığa çıkmıştı):
   Telegram → @BotFather → `/mybots` → botun → API Token → **Revoke**.
   Yeni token'ı bir yere not et. Chat ID'n değişmez.
2. Safari → **github.com** → Zenith depon → dal seçiciden
   `claude/kanka-trading-bot-7goon0` → **Code → Codespaces → Create**.
3. Açılan terminalde:
   ```bash
   cd trading_bot
   cp .env.example .env
   nano .env        # TELEGRAM_BOT_TOKEN=yeni-token  ve  TELEGRAM_CHAT_ID=... yaz
   python3 run.py notify-test
   ```
4. Oyna ve öğren (hepsi sahte para / sadece analiz):
   ```bash
   python3 run.py analyze --once
   python3 run.py backtest --strategy sma --source yahoo --symbol XAUUSD --interval 1d
   python3 run.py walkforward --strategy donchian --source yahoo --symbol XAUUSD
   python3 run.py optimize --strategy sma --source binance --symbol BTCUSDT --interval 4h
   ```
- [ ] **Kontrol:** Telefonuna "baglanti testi basarili" ve analiz raporu mesajları düştü.

## FAZ 1 — Bu hafta: sunucu (≈15 dk, ~4-5$/ay)

1. **Hetzner** (hetzner.com/cloud, en küçük sunucu) veya **DigitalOcean**
   hesabı aç; Ubuntu 24.04 ile en ucuz sunucuyu oluştur. IP adresini not et.
   (Tamamen bedava istersen: Oracle Cloud "Always Free" — kayıt daha zahmetli.)
2. App Store → **Termius** (bedava SSH uygulaması) → sunucu IP'si + root
   şifresi/anahtarı ile bağlan.
- [ ] **Kontrol:** Termius'tan sunucuya bağlanıp `ls` yazabiliyorsun.

## FAZ 2 — Sunucu kurulumu (≈10 dk)

Termius'tan sırayla:
```bash
apt update && apt install -y python3 git
git clone -b claude/kanka-trading-bot-7goon0 https://github.com/gyh52ckbw5-creator/Zenith
cd Zenith/trading_bot
cp .env.example .env && nano .env     # token + chat id
./kur.sh                              # servisleri kurar ve baslatir
```
`kur.sh` şunları yapar: bağlantıyı test eder, `zenith-trader` (paper işlemci)
ve `zenith-analyze` (sürekli analiz) systemd servislerini kurar, açılışta
otomatik başlar hale getirir.

Durum bakmak için:
```bash
systemctl status zenith-trader
journalctl -u zenith-trader -f        # canli log
```
- [ ] **Kontrol:** Telefonuna botun "analiz turu" mesajı geldi; `systemctl status` iki serviste de `active (running)` diyor.

## FAZ 3 — 30-60 gün PAPER koşusu (para YOK)

Haftada bir Termius'tan:
```bash
cd Zenith/trading_bot
python3 run.py report --html          # karne + grafik
cat trades_*.csv                      # islem gunlugu
```
Not defterine yaz: toplam değer, işlem sayısı, en kötü düşüş.
- [ ] **Kontrol / geçiş kriteri:** Bot 30+ gün kesintisiz koştu, davranışını
  anlıyorsun, sonuç al-ve-tut'tan utanç verici şekilde kötü değil.

## FAZ 4 — 1-2 ay TESTNET (gerçek emir, sahte para)

1. **testnet.binance.vision** → GitHub ile giriş → API anahtarı oluştur.
2. Sunucuda `.env`'e ekle: `BINANCE_API_KEY=...` ve `BINANCE_API_SECRET=...`
3. Servisi testnet'e çevir:
   ```bash
   sudo sed -i 's/--mode paper/--mode testnet/' /etc/systemd/system/zenith-trader.service
   sudo systemctl daemon-reload && sudo systemctl restart zenith-trader
   ```
- [ ] **Kontrol / geçiş kriteri:** 60 gün sonunda maksimum düşüş < %15 ve
  kâr faktörü > 1.2 (CSV'den hesaplanır). Sağlanmadıysa FAZ 5 YOK —
  strateji ayarlarına dön, tekrar dene. Bu bir başarısızlık değil, sistemin
  seni korumasıdır.

## FAZ 5 — Karar noktası (belki hiç gelmez, sorun değil)

Ancak FAZ 3+4 kriterleri sağlandıysa:
1. Binance'te gerçek hesap → API anahtarı **sadece spot trade** izni,
   **withdraw KAPALI**, mümkünse IP kısıtlaması sunucu IP'sine.
2. **Kaybetmeyi göze aldığın** küçük tutar yatır (kira/fatura parası ASLA).
3. `.env`'de anahtarları değiştir; serviste `--mode live` + `--riski-anladim`.
4. İlk ay pozisyon limitlerini yarıya indir: `--risk-pct 0.5`.

## Altın kurallar (her fazda geçerli)

- Bot senin kurallarını uygular; para basma makinesi değildir.
- "Bu ay kötü geçti, riski artırayım" = hesabın sonu. Kural değişikliği
  sadece yeni bir FAZ 3 koşusuyla test edilir.
- Anahtarlar sadece `.env`'de yaşar; kimseyle, hiçbir "destek elemanıyla"
  paylaşılmaz. Para asla başkasının "platformuna" gönderilmez.
