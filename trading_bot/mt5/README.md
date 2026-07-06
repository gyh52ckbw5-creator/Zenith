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
| RiskPercent | 1.0 | İşlem başına riske edilen bakiye yüzdesi |
| StopLossPoints | 2000 | Stop-loss mesafesi (puan; EURUSD'de 2000 puan = 200 pip) |
| TakeProfitPoints | 4000 | Kâr al mesafesi (2:1 ödül/risk) |
| MagicNumber | 20260706 | EA'nın kendi işlemlerini tanıma imzası |

## Uyarılar

- Strateji Sınayıcı'da parametreyle oynayıp geçmişte en iyi sonucu bulmak
  **overfitting**'dir; gelecekte çuvallar. Python taraftaki `scan` komutunun
  eğitim/doğrulama ayrımı tam bu yüzden var.
- Gerçek hesaba geçiş kararı, en az birkaç ay **demo** performansından
  sonra verilir. Kaldıraçlı işlemler Türkiye'de SPK düzenlemesine tabidir;
  sadece [SPK yetkili kurumlarla](https://spk.gov.tr) çalış.
- Bu kod eğitim amaçlıdır, yatırım tavsiyesi değildir.
