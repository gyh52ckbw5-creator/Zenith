# Trading Bot — Gerçekler ve Eğitim Amaçlı Başlangıç Kiti

> **Kuruluma başlamak için: [KURULUM.md](KURULUM.md)** — telefondan sunucuya,
> sıralı ve tik atmalı plan. Sunucuda tek komut kurulum: `./kur.sh`

> **ÖNEMLİ:** Varsayılan modlar **gerçek para ile işlem açmaz** (live modu
> bilinçli olarak iki kilit ister). Amaç, sosyal medyada gördüğün "otomatik
> al-sat botu" işinin **gerçekte nasıl çalıştığını** kendi gözünle görmen.

## Komutlara hızlı bakış

| Komut | Ne yapar |
|---|---|
| `backtest` | Stratejiyi geçmiş veride test eder (komisyon/kayma + canlıyla aynı risk bazlı pozisyon boyutu) |
| `chart` | Backtest + equity eğrisi grafikli HTML rapor |
| `scan` | 13 strateji kombinasyonunu tarar, overfit'i işaretler |
| `walkforward` | Ardışık dönem doğrulaması (profesyonel standart) |
| `optimize` | Parametre arama, walk-forward puanlamalı |
| `analyze` | Sürekli analiz + Telegram raporu (bot boştayken bile) |
| `trade` | Otomatik işlem: paper → testnet → live, tam risk yönetimli |
| `report` | Portföy durumu (`--html` ile grafik) |
| `readiness` | Demo/testnet günlüğünden canlıya hazırlık kapısı ve HTML grafik |
| `notify-test` | Telegram kurulumu ve testi |

## 1. TikTok / Instagram'da gördüklerin hakkında acı gerçek

Araştırmanın özeti — bunu okumadan tek satır kod çalıştırma:

1. **O videolardaki "kazanç" ekranlarının çoğu sahte veya seçilmiş.** Demo
   hesap görüntüsü, düzenlenmiş ekran görüntüsü veya 100 denemeden kârlı
   çıkan 1 tanesi gösterilir. Kaybedilen 99 video paylaşılmaz.
2. **Fenomenlerin asıl gelir modeli trading değil, SENSİN.** Broker'lara
   üye kaydettikçe komisyon (IB/affiliate) alırlar, kurs ve "sinyal grubu"
   satarlar. Sen kaybetsen de onlar kazanır — teşvikler tamamen ters yönde.
3. **İstatistik acımasız:** kaldıraçlı forex/CFD hesaplarının kabaca
   **%70-80'i para kaybeder**. Bu oran Avrupa'da broker'ların kendi
   sitelerinde yasal zorunlulukla yazar. ABD'de 2024'te yatırım
   dolandırıcılığı kaybı **5,7 milyar dolar** ile şikâyet listesinin
   birincisiydi.
4. **"Garantili kazanç", "%95 isabet", "ayda %30"** ifadelerinin tamamı
   kırmızı bayraktır. Gerçekten böyle bir botu olan biri onu sana 50
   dolara satmaz; sessizce kendi parasını katlar.
5. **Türkiye'de yasal durum (SPK):** Kaldıraçlı işlemler (forex/CFD)
   yalnızca **SPK yetkili aracı kurumlar** üzerinden yapılabilir. Yurtdışı
   broker'ların Türkiye'de yerleşiklere pazarlama yapması yasaktır; SPK bu
   siteleri düzenli olarak erişime engelletir. İzinsiz aracılık yapanlara
   2-5 yıl hapis ve ağır para cezası öngörülür. Instagram'dan sana yurtdışı
   broker + "botlu hazır sistem" satan kişi büyük ihtimalle bu kapsamda.
6. **En yaygın dolandırıcılık senaryosu:** para senin adına değil,
   dolandırıcının kontrolündeki "platforma" yatırılır → panelde sahte kâr
   gösterilir → para çekmek istediğinde "vergi/komisyon yatır" denir →
   platform kapanır. Meşru hiçbir bot senden **kendi hesabına para
   yatırmanı** istemez; sadece SENİN hesabına API ile bağlanır.

## 2. Peki işin gerçeği ne? Algoritmik trading gerçekten var mı?

Evet, var ve meşru bir alan. Ama gerçeği şöyle:

- **MetaTrader 5 (MT5)** dünyanın en yaygın perakende işlem platformudur.
  Üzerinde **Expert Advisor (EA)** denen robotlar çalışır; bunlar **MQL5**
  dilinde yazılır. MT5 ayrıca resmî **Python kütüphanesi** sunar
  (`pip install MetaTrader5` — sadece **Windows**'ta çalışır), böylece
  stratejiyi Python'da yazıp MT5 terminali üzerinden emir gönderebilirsin.
- Bot dediğin şey sihir değildir; **senin yazdığın kuralları** duygusuz ve
  yorulmadan uygular. Kural kötüyse bot da para kaybettirir — sadece daha
  hızlı ve istikrarlı kaybettirir.
- Profesyonellerin işi %10 strateji, %90 **risk yönetimi, maliyet hesabı ve
  test disiplinidir**: komisyon, spread, kayma (slippage), maksimum düşüş
  (drawdown), aşırı uyum (overfitting)...

## 3. Bu kit ne yapıyor?

```
trading_bot/
├── bot/
│   ├── data.py        # Veri: sentetik üretim, CSV, Binance halka açık API (sadece okuma)
│   ├── indicators.py  # SMA, EMA, RSI
│   ├── strategies.py  # SMA kesişimi, RSI ortalamaya dönüş, al-ve-tut
│   ├── backtest.py    # Komisyon + kayma dahil, look-ahead'siz backtest motoru
│   ├── scanner.py     # OTOMATİK ARAŞTIRMA: sembol×strateji×parametre tarama + overfit tespiti
│   ├── risk.py        # Pozisyon boyutu, stop-loss/take-profit, günlük zarar freni
│   ├── exchange.py    # Binance spot istemcisi (paper/testnet/live)
│   └── trader.py      # Otomatik işlem döngüsü: analiz → karar → risk → emir
├── run.py             # Komut satırı arayüzü
└── README.md
```

Hiçbir ek paket gerekmez (saf Python 3.10+).

### Otomatik araştırma (scan)

Bütün sembol × strateji × parametre kombinasyonlarını tarar. Veriyi
%70 eğitim / %30 doğrulama diye böler; geçmişte parlak görünüp hiç
görmediği veride çökenleri **OVERFIT!** diye işaretler:

```bash
python run.py scan --symbols BTCUSDT,ETHUSDT --interval 4h
```

### Otomatik işlem (trade) — üç kademeli güvenlik

| Mod | Emir | Para | Anahtar |
|---|---|---|---|
| `paper` | simülasyon | sanal | gerekmez |
| `testnet` | gerçek API emri | **sahte** (testnet.binance.vision) | ücretsiz testnet anahtarı |
| `live` | gerçek API emri | **GERÇEK** | kendi Binance anahtarın + `--riski-anladim` bayrağı |

```bash
python run.py trade --mode paper --strategy sma --symbol BTCUSDT --interval 1h
```

Her turda: sinyal üretir → stop-loss/take-profit kontrol eder → pozisyonu
risk kuralına göre boyutlandırır (varsayılan: işlem başına sermayenin %1'i
riskte, tek pozisyon en çok %25, günlük zarar %5'i aşarsa o gün durur) →
emri uygular ve durum dosyasına kaydeder.

Strateji sinyali yalnızca kapanmış mumdan üretilir; açık pozisyonun yazılımsal
stopu ve günlük zarar freni varsayılan olarak her 60 saniyede kontrol edilir
(`--poll-seconds`). Borsa cevabındaki gerçek ortalama dolum fiyatı kaydedilir.
`paper`, `testnet` ve `live` durumları ayrı dosyalardadır; sanal pozisyon canlı
pozisyon olarak yüklenmez.

`live` için: Binance'te API anahtarını **sadece spot trade izniyle** oluştur
(para çekme iznini asla açma), `BINANCE_API_KEY` / `BINANCE_API_SECRET`
ortam değişkenlerine koy. Anahtarları asla koda veya git'e yazma.

### Ayarlar: `.env` dosyası

Anahtarlar `trading_bot/.env` dosyasından otomatik yüklenir (git'e gitmez):

```bash
cp .env.example .env   # sonra icini kendi degerlerinle doldur
```

### Telegram bildirimi kurulumu (tek komut)

1. Telegram'da **@BotFather** → `/newbot` → token'ı al, `.env`'e
   `TELEGRAM_BOT_TOKEN=...` olarak yaz.
2. Telegram'da **kendi botuna** herhangi bir mesaj at (ör. "selam").
3. Çalıştır:

```bash
python run.py notify-test
```

Komut chat ID'ni kendisi bulur, sana söyler ve telefonuna test mesajı
atar. Bulduğu ID'yi `.env`'e `TELEGRAM_CHAT_ID=...` olarak ekle — artık
bot her işlem açtığında/kapattığında ve günlük zarar freni devreye
girdiğinde telefonuna mesaj gelir.

> Güvenlik: bot token'ını kimseyle paylaşma (ekran görüntüsü dahil).
> Paylaştıysan @BotFather → `/mybots` → API Token → **Revoke** ile
> yenile ve `.env`'i güncelle.

### Backtest çalıştır (internet gerekmez)

```bash
cd trading_bot
python run.py backtest --strategy sma --source synthetic
python run.py backtest --strategy rsi --source synthetic --seed 7
```

Backtest, chart, scan, walk-forward, optimize ve Monte Carlo varsayılan olarak
canlı botla aynı `%1` işlem riski, `%2` stop, `%4` hedef ve `%25` tek-pozisyon
tavanını kullanır. Böylece geçmiş testte tüm sermayeyle girip canlıda küçük
pozisyon açan iki farklı sistem karşılaştırılmaz. Örnek daha temkinli ayar:

```bash
python run.py backtest --strategy sma --source synthetic \
  --risk-pct 0.5 --stop-loss 2 --take-profit 4 --max-position 20
```

### Gerçek veriyle backtest (Binance halka açık verisi, hesap gerekmez)

```bash
python run.py backtest --strategy sma --source binance --symbol BTCUSDT --interval 4h
```

### Paper trading — sanal cüzdanla canlı takip

```bash
python run.py paper --strategy sma --symbol BTCUSDT --interval 1h
```

Sanal cüzdan `paper_state.json` dosyasında tutulur. Emir gönderilmez;
sadece "şu an alırdım/satardım" kararları ve sanal bakiye izlenir.

### Testler

```bash
pytest tests/test_trading_bot.py -v
```

### Canlıya hazırlık kapısı

Demo/paper/testnet işlemleri yeterince biriktiğinde örnek sayısı, takvim süresi,
kâr faktörü, işlem başına beklenti, maksimum düşüş, yakın dönem performansı ve
bozuk satır kontrolünü tek komutta çalıştır:

```bash
python run.py readiness --html
```

Varsayılan kapı en az 100 kapanmış işlem, 60 takvim günü, 1.20 kâr faktörü,
pozitif beklenti, en fazla `%10` drawdown ve son 30 işlemde pozitif beklenti
ister. Her koşul geçse bile sonuç kâr garantisi değildir. Otomasyonda kapı
başarısızsa çıkış kodu `2` almak için `--require-pass` ekle.

Kapı `hesap_kz_yuzde` alanını kullanır; yalnızca enstrüman fiyat getirisini
içeren eski günlükler kaldıraç/pozisyon büyüklüğünü bilmediği için güvenli
tarafta kalıp veri kalitesi kontrolünden geçmez.

## 4. Kendi gözünle görmen gereken dersler

Bu kiti kurcalarken şunları dene, sosyal medyanın anlatmadığı her şeyi
kendin keşfedeceksin:

1. **Komisyonu aç-kapa:** `--commission 0 --slippage 0` ile "kârlı" görünen
   strateji, gerçekçi maliyetlerle nasıl eriyor gör.
2. **Seed değiştir:** `--seed 1,2,3...` ile aynı strateji farklı piyasa
   koşullarında bambaşka sonuç verir. Tek bir güzel grafik hiçbir şey
   kanıtlamaz.
3. **Al-ve-tut ile kıyasla:** çıktıda her zaman "al-ve-tut getirisi"
   gösterilir. Botların çoğu, hiçbir şey yapmamanın gerisinde kalır.
4. **Parametre oynama tuzağı:** `--fast/--slow` değerlerini geçmiş veride
   en iyi sonucu verene kadar ayarlarsan, geleceğe değil **geçmişe uyum
   sağlamış** (overfit) olursun. Gelecekte çuvallar.

## 5. Buradan sonra ciddi yol haritası

1. **6-12 ay sadece paper trading / demo hesap.** Gerçek para yok.
2. Python + istatistik öğren; "Advances in Financial Machine Learning"
   (Lopez de Prado) ve Ernest Chan'in kitapları iyi başlangıçtır.
3. MT5 yolu: Windows'ta MT5 kur → **demo hesap** aç → MQL5 ile basit EA yaz
   veya resmî `MetaTrader5` Python paketiyle bağlan → **Strateji Sınayıcı**
   (Strategy Tester) ile yıllarca veri üzerinde test et.
4. Kripto yolu: borsaların **testnet**'lerinde (ör. Binance Spot Testnet)
   API ile sahte parayla emir göndermeyi öğren.
5. Gerçek paraya geçersen: **kaybetmeyi göze aldığın küçük tutar**, SPK
   yetkili kurum (kaldıraçlı işlemler için) ve pozisyon başına sermayenin
   %1-2'sinden fazla risk yok. "Zengin olma" değil "hayatta kalma" hedefi.

## 6. Yol haritası (plan/proje)

**Bitenler:**
- [x] Backtest motoru (komisyon/kayma dahil, look-ahead'siz) + kâr faktörü, Sharpe, drawdown
- [x] 4 strateji: SMA kesişimi, EMA kesişimi, RSI dönüşü, Donchian kırılımı (Turtle)
- [x] Otomatik tarama (`scan`): eğitim/doğrulama ayrımı + overfit tespiti
- [x] **Walk-forward testi** (`walkforward`): profesyonel fonların doğrulama standardı —
  tek bölme şans eseri iyi çıkabilir, strateji ancak ardışık dilimlerin çoğunda
  ayakta kalıyorsa güvenilirdir
- [x] Risk yönetimi: pozisyon boyutu, stop-loss/take-profit, **iz süren stop**
  (`--trailing-stop`), günlük zarar freni
- [x] Otomatik işlem döngüsü: paper/testnet/live, çoklu sembol, kesinti dayanıklılığı
- [x] Telegram bildirimleri + tek komutla kurulum (`notify-test`)
- [x] Portföy raporu (`report`)
- [x] MT5 Expert Advisor (MQL5) + kurulum rehberi

- [x] ATR tabanlı dinamik stop (`--atr-stop 2.0`: stop mesafesi oynaklığa uyum sağlar)
- [x] Trend filtresi (`--trend-filter 200`: fiyat SMA200 altındayken alım yasak)
- [x] İşlem günlüğü CSV çıktısı (`trades_SEMBOL.csv`, kapanan her işlem)
- [x] Canlı sinyalde kapanmamış mum düzeltmesi (sinyal yalnızca kapanan mumdan üretilir)
- [x] Sunucuda 7/24 çalıştırma rehberi (aşağıda)

- [x] Forex/altın veri kaynağı (Yahoo Finance: EURUSD, XAUUSD, USDTRY... anahtar gerekmez)
- [x] Sürekli analiz modu (`analyze`): bot boştayken bile düzenli tarar, Telegram'a rapor atar
- [x] Ücretsiz AI yorumcu (isteğe bağlı, OpenRouter)
- [x] Equity eğrisi HTML raporu (`chart`)
- [x] Binance LOT_SIZE/stepSize otomatik yuvarlama
- [x] Bollinger + MACD stratejileri (tarama ızgarası 13 kombinasyona çıktı)
- [x] Korumalar: cooldown + stop-loss guard (freqtrade Protections uyarlaması)

**Sırada:**
- [ ] Equity eğrisi grafiği (HTML rapor)
- [ ] Emir miktarında borsa hassasiyet kuralları (LOT_SIZE/stepSize otomatik yuvarlama)
- [ ] Binance testnet'te 1-2 aylık gerçek zamanlı doğrulama koşusu ← **asıl kilometre taşı**

### Forex / altın verisi (MT5 pariteleri)

`USDT` ile biten semboller Binance'ten (kripto), diğerleri Yahoo Finance'ten
(forex/altın) otomatik çekilir — MT5'te gördüğün USD paritelerinin verisi:

```bash
python run.py backtest --strategy sma --source yahoo --symbol EURUSD --interval 1d
python run.py walkforward --strategy donchian --source yahoo --symbol XAUUSD --interval 1d
```

Kısayollar: `XAUUSD`/`GOLD`/`ALTIN` → altın, `XAGUSD` → gümüş,
6 harfli pariteler (`EURUSD`, `USDTRY`...) otomatik tanınır.
Not: Yahoo verisiyle sadece analiz yapılır; forex'te gerçek işlem MT5 +
SPK yetkili kurum gerektirir (`mt5/` klasörüne bak).

### Sürekli analiz modu (bot boştayken bile çalışır)

```bash
python run.py analyze --symbols BTCUSDT,ETHUSDT,EURUSD,XAUUSD --interval 1d --every-hours 6
```

Her turda tüm sembol × strateji kombinasyonlarını tarar (eğitim/doğrulama
ayrımı + overfit tespitiyle), en iyi 3'ü ve elemeyi geçen adayı hem ekrana
yazar hem Telegram'dan cebine gönderir. `--once` ile tek tur çalışır.
systemd ile ikinci bir servis olarak 7/24 koşturulabilir.

### Ücretsiz AI yorumcu (isteğe bağlı)

[openrouter.ai](https://openrouter.ai)'dan ücretsiz anahtar alıp `.env`'e
`OPENROUTER_API_KEY=...` yazarsan, `analyze` raporlarına ücretsiz bir
yapay zekâ modelinin (varsayılan: DeepSeek) temkinli risk-yöneticisi
yorumu eklenir ve Telegram mesajına dahil edilir. AI yorumu da tahmindir;
karar mercii her zaman risk kurallarıdır.

## 6b. Sunucuda 7/24 çalıştırma (systemd)

Ev bilgisayarı kapanınca bot durur. Ayda ~5$'a bir Linux sunucuda
(Hetzner/DigitalOcean) kesintisiz çalıştırmak için `/etc/systemd/system/zenith-bot.service`:

```ini
[Unit]
Description=Zenith trading bot (paper)
After=network-online.target

[Service]
WorkingDirectory=/home/kullanici/Zenith/trading_bot
ExecStart=/usr/bin/python3 run.py trade --mode paper --symbols BTCUSDT,ETHUSDT --strategy sma
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now zenith-bot   # baslat + acilista otomatik
journalctl -u zenith-bot -f              # canli log izle
```

Bot çökse/sunucu yeniden başlasa bile `Restart=always` + durum dosyaları
sayesinde kaldığı yerden devam eder; işlemler Telegram'dan cebine düşer.

## 6c. Korumalar (freqtrade'in Protections sisteminden uyarlama)

`trade` komutunda varsayılan olarak açık iki koruma daha var:

- **Cooldown** (`--cooldown 3`): stop yedikten sonra 3 mum boyunca yeni
  giriş yasak. Amaç, kaybı hemen geri alma dürtüsüyle yapılan "intikam
  işlemini" engellemek — hesap batıran davranışların başında gelir.
- **Stop-loss guard** (`--stoploss-guard 3`): aynı gün 3 kez stop
  yenirse bot o günü tamamen kapatır. O gün piyasa senin stratejinle
  uyumsuz demektir; ısrar etmek çözüm değildir.

## 6d. Açık kaynak dünyası: bu kitten sonrası

Bu kit öğrenmek için; ciddileşince tekerleği yeniden icat etme, olgun
açık kaynak projelere geç:

| Proje | Ne işe yarar | Not |
|---|---|---|
| [freqtrade](https://www.freqtrade.io) | Kripto sinyal botu (25k+ yıldız) | Hyperopt optimizasyonu, FreqAI ML, Telegram kontrolü, koruma sistemi — bizim kitin endüstriyel hali |
| [Hummingbot](https://hummingbot.org) | Market making (piyasa yapıcılık) | Alış-satış makası kazancı; farklı bir oyun, ileri seviye |
| [Jesse](https://jesse.trade) | Backtest odaklı framework | Look-ahead bias'sız motor — bizim motorla aynı felsefe |
| [OctoBot](https://www.octobot.cloud) | Başlangıç dostu bot | Kod yazmadan kullanılabiliyor |
| [vectorbt](https://vectorbt.dev) | Çok hızlı toplu backtest | Binlerce parametre kombinasyonunu dakikalar içinde tarar |
| [ccxt](https://github.com/ccxt/ccxt) | 100+ borsa API kütüphanesi | Bizim `exchange.py`'nin çok-borsalı devi |

Uyarı: freqtrade topluluğunun hazır stratejileri de (NostalgiaForInfinity
vb.) geçmişe göre ayarlanmıştır — hangisini alırsan al, kendi walk-forward
testinden geçirmeden canlıya yaklaştırma.

## 7. Yasal uyarı

Bu yazılım ve belge yatırım tavsiyesi değildir; yalnızca eğitim amaçlıdır.
Kaldıraçlı işlemler sermayenin tamamının kaybıyla sonuçlanabilir. Türkiye'de
kaldıraçlı alım satım işlemleri SPK düzenlemelerine tabidir; işlem yapmadan
önce aracı kurumun yetki belgesini [spk.gov.tr](https://spk.gov.tr)
üzerinden doğrulayın.
