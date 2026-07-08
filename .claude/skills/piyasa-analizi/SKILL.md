---
name: piyasa-analizi
description: >
  Zenith trading_bot araclariyla durust piyasa analizi yap. Kullanici
  "piyasa analizi", "tara", "strateji test et", "backtest", "optimize et",
  "portfoy durumu", "bot nasil gidiyor" gibi bir sey istediginde bu skill'i
  kullan. Arac zinciri: scan -> walkforward -> optimize -> backtest/chart ->
  report. Sonuclari overfit ve al-ve-tut kiyasiyla yorumla; asla kazanc
  garantisi verme.
---

# Piyasa Analizi — Zenith trading_bot is akisi

Tum komutlar `trading_bot/` dizininden calisir: `cd trading_bot && python3 run.py ...`
Anahtarlar `.env`'den otomatik yuklenir. Hicbir analiz komutu gercek emir gondermez.

## Sembol kurallari

- `USDT` ile bitenler -> Binance kripto (BTCUSDT, ETHUSDT...)
- Digerleri -> Yahoo: forex (EURUSD, USDTRY), altin (XAUUSD/GOLD), hisse
- Kisayollar: `FOREX`, `KRIPTO`, `HEPSI` (run.py icindeki SYMBOL_PRESETS)

## Standart analiz akisi (kullanici "analiz yap" deyince)

1. **Genis tarama:** `python3 run.py scan --symbols HEPSI --interval 1d`
   - Cikti egitim/dogrulama ayrimlidir; `OVERFIT!` etiketlilere guvenme.
   - "Elemeyi gecen aday yok" da GECERLI bir sonuctur: beklemek karardir.
2. **Adayi dogrula:** en iyi aday icin
   `python3 run.py walkforward --strategy <s> --source yahoo|binance --symbol <sym> --interval 1d`
   - Dilimlerin cogunda artida degilse aday elenmistir; bunu acikca soyle.
3. **Ince ayar (istenirse):**
   `python3 run.py optimize --strategy <s> --source ... --symbol <sym> --trials 30`
   - Puan walk-forward medyanidir; tek donem sampiyonlarini one cikartma.
4. **Gorsel rapor (istenirse):** `python3 run.py chart ...` HTML uretir;
   kullaniciya dosyayi gonder.

## Portfoy/bot durumu sorulursa

- `python3 run.py report` (ozet) veya `report --html` (grafik dosyasi)
- Islem gecmisi: `trading_bot/trades_*.csv`
- Calisan bot loglari: `trader_state_*.json` icindeki `log` alani

## Yorumlama kurallari (pazarlik yok)

- Her sonucu **al-ve-tut kiyasiyla** ver; strateji al-ve-tutu gecemiyorsa bunu sakla-ma.
- Maksimum dusus (DD) ve islem sayisini mutlaka soyle; <5 islemli parlak
  sonuc "kucuk orneklem" uyarisiyla verilir.
- Kesin dil yasak: "kazandirir" degil "gecmis veride soyle davrandi".
- Kullanici canli islem/para yatirma konusuna gelirse: once
  `trading_bot/KURULUM.md` fazlarini ve gecis kriterlerini hatirlat
  (paper -> testnet -> kriter sartli live). Live mod ancak kullanicinin
  kendi anahtarlari + `--riski-anladim` bayragiyla calisir; bu bayragi
  kullanici adina ekleme, ONCE teyit iste.
- Forex sorularinda `trading_bot/FOREX.md`'deki SPK/yasal cerceveyi dikkate al.

## Bildirimler

Telegram ayarliysa (`.env`) `analyze` ve `trade` olaylari kullanicinin
telefonuna gider. Baglanti sorunu varsa `python3 run.py notify-test` calistir.
