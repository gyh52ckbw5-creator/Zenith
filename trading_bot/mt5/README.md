# MetaTrader 5 Expert Advisor — ZenithSmaEA

TikTok'ta gördüğün "ChatGPT'den kod al, MetaEditor'e yapıştır" videolarının
**derlenen, risk yönetimli, temiz** versiyonu. Python taraftaki
`SmaCross` stratejisinin MQL5 hali: hızlı SMA yavaşı yukarı kesince alır,
aşağı kesince kapatır; her pozisyona otomatik stop-loss/take-profit koyar
ve lot büyüklüğünü "işlem başına bakiyenin %1'i riskte" kuralıyla hesaplar.

> **Not:** MQL5 sadece Windows'taki MetaEditor'de derlenir; bu depoda
> derleyici yok. Aşağıdaki adımlarla kendin derleyeceksin — hata çıkarsa
> mesaj at, düzeltirim.

## Kurulum (adım adım)

1. **MT5'i indir** → [metatrader5.com](https://www.metatrader5.com/) →
   kur, açılışta **DEMO HESAP** oluştur (broker: MetaQuotes-Demo olur).
2. MT5 içinde **Araçlar → MetaQuotes Language Editor** (F4) ile
   MetaEditor'ü aç.
3. Sol paneldeki **MQL5 → Experts** klasörüne sağ tık → *New File* →
   *Expert Advisor (template)* → adı `ZenithSmaEA` yap → oluşan dosyanın
   içeriğini SİL, bu klasördeki `ZenithSmaEA.mq5` içeriğini yapıştır.
4. **F7 (Compile)** → altta "0 errors, 0 warnings" görmelisin.
   (TikTok'taki videoda adamın ekranında "19 errors" yazıyordu —
   derlenmeyen kod işlem açamaz, o yüzden önce burası.)
5. MT5'e dön → **Görünüm → Strateji Sınayıcı** (Ctrl+R):
   - Expert: ZenithSmaEA, Sembol: EURUSD, Periyot: H1
   - Tarih: en az 3-5 yıl geriden başlat
   - "Her tik" yerine "OHLC 1 dakika" hızlı ve yeterli
   - **Başlat** → sonuç raporunda net kâr, maksimum düşüş (drawdown),
     kâr faktörü ve işlem listesini incele.
6. Testte beğendiysen: grafiğe sürükle → "Algo Trading" düğmesini aç →
   **demo hesapta** haftalarca çalıştır, davranışını izle.

## Parametreler

| Parametre | Varsayılan | Anlamı |
|---|---|---|
| FastPeriod / SlowPeriod | 20 / 50 | SMA periyotları |
| UseTrendFilter / TrendPeriod | true / 200 | Fiyat SMA200 altındayken alım yasak |
| RiskPercent | 1.0 | İşlem başına riske edilen bakiye yüzdesi |
| StopLossPoints | 2000 | Stop-loss mesafesi (puan; EURUSD'de 2000 puan = 200 pip) |
| TakeProfitPoints | 4000 | Kâr al mesafesi (2:1 ödül/risk) |
| TrailingStopPoints | 0 | İz süren stop (0 = kapalı); SL'i sadece lehine taşır |
| MaxDailyLossPercent | 5.0 | Günlük zarar freni: aşılırsa o gün işlem yok |
| CooldownBars | 3 | Pozisyon kapandıktan sonra N mum yeni giriş yok |
| MaxSpreadPoints | 50 | Spread bu sınırı aşarsa yeni pozisyon açılmaz |
| AllowLiveAccount | false | Canlı hesapta kazara çalışmayı engeller |
| LiveAccountLogin | 0 | Canlıda izin verilen tam MT5 hesap numarası |
| MaxMarginPercent | 20 | Tek emrin kullanabileceği azami equity/marjin oranı |
| AllowWeekendEntry | false | Cuma geç saat/hafta sonu yeni giriş kilidi |
| FridayCutoffHourUTC | 18 | Cuma yeni girişlerin kesildiği UTC saati |
| MagicNumber | 20260708 | EA'nın kendi işlemlerini tanıma imzası |

Forex'e özel notlar ve Türkiye'deki yasal çerçeve için: [../FOREX.md](../FOREX.md)

## Python MT5 köprüsü güvenlik kontrolleri

`mt5_bridge.py`, açık Windows MT5 terminaline bağlanan alternatif demo ve
canlı çalıştırıcısıdır. Varsayılan hesap modu `demo`dur. Her yeni emirden önce:

- yalnızca yeni kapanmış mumda bir kez karar verir;
- kotasyonun son 30 saniye içinde geldiğini doğrular;
- spread 50 broker puanını aşarsa alım yapmaz;
- Cuma UTC 18:00 sonrası ve hafta sonu yeni pozisyon açmaz;
- broker stop mesafesini, gerekli marjini ve `order_check` sonucunu doğrular;
- lotu her turda yenilenen güncel hesap equity'sinden hesaplar;
- günlük equity kaybı varsayılan `%3` sınırına gelince kendi pozisyonunu
  kapatır ve günün kalanında yeni emir açmaz.

Koruma durumu `.mt5_bridge_state_<SEMBOL>_<MAGIC>.json` dosyasına atomik
olarak yazılır; program yeniden başlasa da aynı mumda tekrar emir vermez ve
günlük fren unutulmaz.

Kapanan MT5 işlemleri `trades_mt5_<SEMBOL>_<MAGIC>.csv` günlüğüne yazılır.
Günlük yazılamazsa köprü yeni alımları engeller; eksik performans verisiyle
canlıya hazır görünmez. Demo koşusu yeterince biriktiğinde:

```bash
python run.py readiness --mode demo --html
```

Örnek demo çalıştırması:

```bash
python mt5/mt5_bridge.py --symbol EURUSD --interval M15 \
  --risk-pct 0.5 --max-daily-loss 2 --max-spread-points 30
```

Canlı hesap iki aşamalı çalıştırılır. Önce yalnızca teknik ve hesap
kontrollerini yapan, **emir döngüsünü başlatmayan** preflight:

```bash
python mt5/mt5_bridge.py --symbol EURUSD --interval M15 \
  --account-mode live --allow-live --live-account 12345678 \
  --live-ack CANLI_RISKI_KABUL --preflight-only
```

`PREFLIGHT OK` görmeden canlı çalıştırma yapma. Sonraki komutta yalnızca
`--preflight-only` kaldırılır. Hesap numarası açık MT5 hesabıyla birebir
eşleşmezse veya açık onay metni eksikse program kapanır. EA kullanılacaksa
aynı koruma için `AllowLiveAccount=true` ve `LiveAccountLogin` alanına tam
hesap numarası birlikte girilir.

Altın ve bazı broker sembollerinde puan ölçeği farklıdır. Demo günlüğünde
normal spread'i gözlemleyip `--max-spread-points` değerini sembole göre ayarla;
korumayı kaldırmak yerine gerçekçi bir üst sınır kullan.

## Uyarılar

- Strateji Sınayıcı'da parametreyle oynayıp geçmişte en iyi sonucu bulmak
  **overfitting**'dir; gelecekte çuvallar. Python taraftaki `scan` komutunun
  eğitim/doğrulama ayrımı tam bu yüzden var.
- Gerçek hesaba geçiş kararı, en az birkaç ay **demo** performansından
  sonra verilir. Kaldıraçlı işlemler Türkiye'de SPK düzenlemesine tabidir;
  sadece [SPK yetkili kurumlarla](https://spk.gov.tr) çalış.
- Bu kod eğitim amaçlıdır, yatırım tavsiyesi değildir.
