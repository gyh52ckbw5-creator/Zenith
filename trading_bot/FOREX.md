# FOREX Rehberi — Türkiye'den Gerçekçi Yol Haritası

Forex'e odaklanmak istiyorsan önce oyunun kurallarını bil. Bu rehber üç şeyi
anlatır: yasal zemin, forex'in kripto'dan farkları, ve bu depodaki araçlarla
forex'i nasıl çalışacağın.

## 1. Yasal zemin (Türkiye) — pazarlıksız kurallar

- Kaldıraçlı forex/CFD işlemleri Türkiye'de **yalnızca SPK yetkili aracı
  kurumlar** üzerinden yapılabilir. Yetkili kurum listesi:
  [spk.gov.tr](https://spk.gov.tr) → Yetkili Kuruluşlar.
- SPK kuralları: perakende yatırımcıda kaldıraç **en fazla 10:1**,
  başlangıç teminatı asgari **50.000 TL** civarındadır (güncel rakamı
  kurumdan doğrula).
- Instagram/Telegram'dan ulaşan **yurtdışı broker'lar Türkiye'de yasa dışı
  faaliyettir**; para yatırırsan hukuki korunman yoktur ve çoğu düpedüz
  dolandırıcılıktır. "Bot kurulumu + yurtdışı hesap" paketi satan herkesten uzak dur.
- **Demo hesap için hiçbir şart yok:** MT5 indir, MetaQuotes-Demo ile
  sınırsız ve bedava çalış. Bu depodaki plan zaten aylarca demoda kalmanı söylüyor.

## 2. Forex'in kripto'dan farkları (botunu etkileyenler)

| Konu | Kripto (Binance) | Forex (MT5) |
|---|---|---|
| Piyasa saati | 7/24 | Pazartesi-Cuma; hafta sonu KAPALI |
| Maliyet | komisyon (~%0.1) | spread (alış-satış makası) + swap (gecelik taşıma) |
| Oynaklık | yüksek | majörlerde düşük; haber anlarında ani |
| Kaldıraç | spotta yok | var — hem büyütür hem BATIRIR |
| Bot yolu | Python + API | **MQL5 EA** (bu depoda: `mt5/ZenithSmaEA.mq5`) |

Botun için pratik sonuçları:
- Hafta sonu boşluğu (gap): Cuma kapanışı ile Pazartesi açılışı farklı
  olabilir; stop'un boşlukta atlanabilir. Pozisyonu hafta sonuna taşımamak
  bir seçenektir.
- Spread, senin `--commission/--slippage` bayraklarının karşılığıdır:
  EURUSD'de düşük, egzotiklerde (USDTRY!) çok yüksektir. USDTRY'de scalping
  yapılmaz; spread her işlemde seni yener.
- En likit ve öğrenmeye uygun pariteler: **EURUSD, GBPUSD, USDJPY** + altın
  (**XAUUSD**, oynaklığı yüksektir, riskini ona göre ayarla).

## 3. Bu depoyla forex çalışma akışı

### Analiz/araştırma (Python, her yerde çalışır)

```bash
# Hazir forex listesiyle tarama (FOREX kisayolu acilir: EURUSD,GBPUSD,USDJPY,USDTRY,XAUUSD)
python run.py scan --symbols FOREX --interval 1d
python run.py analyze --symbols FOREX --interval 1d --every-hours 6   # surekli + Telegram

# Tek parite derin analiz
python run.py backtest    --strategy sma      --source yahoo --symbol EURUSD --interval 1d --stop-loss 1 --take-profit 2
python run.py walkforward --strategy donchian --source yahoo --symbol XAUUSD --interval 1d
python run.py optimize    --strategy sma      --source yahoo --symbol EURUSD --interval 1d
```

Not: Forex'te günlük (%1-2'lik) hareketler kriptodan küçüktür; stop/hedef
yüzdelerini ona göre küçült (ör. `--stop-loss 1 --take-profit 2`).

### İşlem (MT5 Expert Advisor)

`mt5/ZenithSmaEA.mq5` v2, Python botundaki risk zincirinin tamamını taşır:
SMA kesişimi + SMA200 trend filtresi + sabit SL/TP + iz süren stop +
günlük zarar freni + cooldown. Kurulum: `mt5/README.md`.

Sıra şöyle:
1. MT5 + **demo hesap** → EA'yı derle (F7) → Strateji Sınayıcı'da EURUSD H1,
   5+ yıl test et.
2. Parametreleri Python `optimize` çıktısıyla karşılaştır; iki dünyada da
   ayakta kalan ayar ara.
3. Demo hesapta EA'yı **en az 2-3 ay** canlı çalıştır (Algo Trading açık).
4. Gerçek paraya geçiş ancak SPK yetkili kurumda ve KURULUM.md Faz 5
   kriterleriyle olur.

## 3b. iPhone'dan forex (Windows bilgisayarın yoksa)

Gerçek durum: **MT5'in iOS uygulaması EA (robot) çalıştıramaz** — EA'lar
yalnızca masaüstü terminalde koşar. iPhone'la bu iş üç parçayla kurulur:

**Adım 1 — Bugün, bedava: MT5 iOS uygulaması (öğrenme + izleme)**
1. App Store → **MetaTrader 5** (MetaQuotes) → indir.
2. Ayarlar → Yeni Hesap → **MetaQuotes-Demo** → demo hesap aç (ücretsiz,
   şartsız, süresiz).
3. EURUSD ve XAUUSD grafiklerini incele; birkaç **manuel demo işlem** yap:
   emir, lot, SL/TP koymayı elinle öğren. Botun ne yaptığını anlamanın
   en hızlı yolu, bir kez elle yapmaktır.

**Adım 2 — Analiz: zaten iPhone'da çalışıyor**
Codespaces/Termius'tan `scan --symbols FOREX`, `walkforward`, `optimize` —
hepsi bu depoda hazır (bkz. bölüm 3).

**Alternatif — Python köprüsü (aynı stratejinin canlı MT5 hali)**
Windows'ta `pip install MetaTrader5` → MT5 demo hesabı aç → `.env`'e
`MT5_LOGIN / MT5_PASSWORD / MT5_SERVER` yaz → `python mt5/mt5_bridge.py
--symbol EURUSD --interval M15`. Köprü bizim stratejiyle demo emri gönderir,
Telegram'a haber verir; telefondaki MT5 uygulamasına aynı demo hesabıyla
girince işlemleri canlı görürsün. Güvenlik: köprü varsayılan olarak SADECE
demo hesapta çalışır (canlı için bilerek `--allow-live` gerekir).

**Adım 3 — EA'yı 7/24 çalıştırmak: Windows VPS + iPhone'dan uzak masaüstü**
1. Windows VPS kirala (~10-15$/ay: Contabo, Kamatera vb. "Windows VPS").
2. App Store → **Windows App** (Microsoft'un resmî RDP istemcisi, bedava)
   → VPS'in IP'si + kullanıcı adı/şifresiyle bağlan. Artık iPhone'unda
   tam bir Windows masaüstü var.
3. O Windows'ta: MT5 kur → demo hesap → MetaEditor'de `ZenithSmaEA.mq5`'i
   derle (F7) → grafiğe ekle → Algo Trading'i aç. VPS hep açık kaldığı
   için EA 7/24 çalışır.
4. **İzleme hilesi:** MT5 iOS uygulamasına AYNI demo hesabıyla gir —
   EA'nın VPS'te açtığı pozisyonlar telefonunda canlı görünür. Yani
   robotu kurarken RDP, izlerken doğal iOS uygulaması.

Bütçe dostu sıra: önce Adım 1+2 (bedava) ile haftalarca öğren; EA'nın
Strateji Sınayıcı testlerini de RDP'siz halledemezsin, o yüzden Windows
VPS'i ancak cebin elverdiğinde ve Python taraftaki paper koşun otururken
ekle. Acele eden forex'e değil, spread'e yem olur.

## 4. Forex'e özel tuzaklar

- **Haber anları:** NFP (ABD tarım dışı istihdam), faiz kararları... Spread
  10 katına çıkar, stop'lar kayarak dolar. **Bot artık bunu biliyor:**
  `trade` komutunda haber karantinası varsayılan açıktır — yüksek etkili
  haberlerin ±30 dakikasında yeni pozisyon açılmaz (ForexFactory ücretsiz
  takvimi; ulaşılamazsa bot durmaz, filtre devre dışı kalır). Kapatmak
  istersen: `--no-news-filter`.
- **Swap:** Gecelik pozisyon taşımanın maliyeti/getirisi vardır; trend
  takibi gibi günlerce taşıyan stratejilerde backtest'in görmediği bir
  maliyettir. Demo döneminde hesap ekstresinden gerçek swap'ı gör.
- **10:1 kaldıraç bile çift taraflı bıçaktır:** %1'lik ters hareket,
  teminatının %10'unu götürür. `RiskPercent=1` kuralı forex'te de geçerli —
  kaldıraç "daha çok kazanma" değil "daha az teminat bağlama" aracıdır.

*Bu belge eğitim amaçlıdır, yatırım tavsiyesi değildir.*
