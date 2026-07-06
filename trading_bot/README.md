# Trading Bot — Gerçekler ve Eğitim Amaçlı Başlangıç Kiti

> **ÖNEMLİ:** Bu klasördeki kod **gerçek para ile işlem açmaz**. Amacı, sosyal
> medyada gördüğün "otomatik al-sat botu" işinin **gerçekte nasıl çalıştığını**
> kendi gözünle görmen: strateji yazmak, geçmiş veride test etmek (backtest) ve
> sanal para ile canlı takip (paper trading).

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
emri uygular ve `trader_state.json`'a kaydeder.

`live` için: Binance'te API anahtarını **sadece spot trade izniyle** oluştur
(para çekme iznini asla açma), `BINANCE_API_KEY` / `BINANCE_API_SECRET`
ortam değişkenlerine koy. Anahtarları asla koda veya git'e yazma.

### Backtest çalıştır (internet gerekmez)

```bash
cd trading_bot
python run.py backtest --strategy sma --source synthetic
python run.py backtest --strategy rsi --source synthetic --seed 7
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

## 6. Yasal uyarı

Bu yazılım ve belge yatırım tavsiyesi değildir; yalnızca eğitim amaçlıdır.
Kaldıraçlı işlemler sermayenin tamamının kaybıyla sonuçlanabilir. Türkiye'de
kaldıraçlı alım satım işlemleri SPK düzenlemelerine tabidir; işlem yapmadan
önce aracı kurumun yetki belgesini [spk.gov.tr](https://spk.gov.tr)
üzerinden doğrulayın.
