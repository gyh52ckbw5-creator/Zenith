# Zenith

Zenith, birden fazla **ücretsiz** yapay zeka modelini (yerel Ollama modelleri +
Groq, Google Gemini, OpenRouter, Cerebras gibi sağlayıcıların ücretsiz
katmanları) tek bir kişisel asistanda birleştiren bir "Jarvis" tarzı
asistandır. Hem terminalden hem de telefonundan (iOS dahil) bir web
uygulaması / PWA olarak kullanılabilir.

Tek bir modele bağımlı kalmak yerine, Zenith şunları yapabilir:

- **Tek model modu**: Öncelik sırasına göre en iyi kullanılabilir modeli
  dener; bir model başarısız olursa (rate limit, hata, kapalı) otomatik
  olarak bir sonrakine geçer (fallback zinciri).
- **Konsey modu (`/council`)**: Aynı soruyu birden fazla ücretsiz modele
  paralel olarak sorar, sonra bir "sentezleyici" model bu cevapları
  birleştirip tek, tutarlı bir nihai cevap üretir. Yani gerçekten
  *"tüm ücretsiz AI modelleri birlikte çalışıyor"*.
- **Hafıza**: Konuşmalar `~/.zenith/memory.json` içinde saklanır, bir
  sonraki oturumda kaldığın yerden devam edersin.
- **Yerel araçlar**: Basit hesaplama (`hesapla: 12*7`) ve saat sorgusu gibi
  komutlar hiç bir modele gitmeden yerel olarak cevaplanır.

## Mimari

```
zenith/
  config.py      # config/models.yaml içindeki model kaydını yükler
  providers.py    # LiteLLM üzerinden herhangi bir sağlayıcıyı çağıran ince katman
  router.py       # tek-model modu: öncelik sıralı fallback zinciri
  council.py      # konsey modu: paralel sorgu + sentez
  memory.py       # dosya tabanlı konuşma hafızası
  tools.py        # yerel, LLM'siz komutlar (hesap makinesi, saat)
  assistant.py    # hepsini birleştiren ZenithAssistant sınıfı
  cli.py          # interaktif terminal arayüzü
  server.py       # FastAPI web/API katmanı (telefon/iOS icin)
static/           # mobil uyumlu sohbet arayüzü + PWA (manifest, service worker, ikonlar)
```

Sağlayıcı çağrıları [LiteLLM](https://github.com/BerriAI/litellm) üzerinden
yapılır; bu sayede Ollama, Groq, Gemini, OpenRouter, Cerebras ve LiteLLM'in
desteklediği 100+ sağlayıcıdan herhangi biri, `config/models.yaml` dosyasına
tek satır eklenerek kullanılabilir hale gelir.

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` dosyasını, sahip olduğun ücretsiz API anahtarlarıyla doldur (hiçbirini
doldurmasan da yerel Ollama ile çalışabilirsin):

| Sağlayıcı | Ücretsiz anahtar nereden alınır |
|---|---|
| Groq | https://console.groq.com/keys |
| Google Gemini | https://aistudio.google.com/apikey |
| OpenRouter (`:free` modeller) | https://openrouter.ai/keys |
| Cerebras | https://cloud.cerebras.ai |
| Ollama (yerel, sınırsız) | https://ollama.com — kurduktan sonra `ollama pull llama3.1` |

Not: Sağlayıcıların ücretsiz katman koşulları zamanla değişebilir;
`config/models.yaml` dosyasını kendi hesabına göre güncelleyebilirsin.

## Kullanım

```bash
python -m zenith
```

```
sen> merhaba, bugün ne yapabilirsin?
zenith> ...

sen> /council
Konsey modu: acik

sen> kuantum bilgisayarları basitçe açıklar mısın?
zenith> (birden fazla ücretsiz model paralel çalışıp cevaplarını birleştirir)
```

Komutlar:

- `/council` — konsey modunu aç/kapat
- `/models` — yapılandırılmış tüm modelleri ve kullanılabilirlik durumlarını listele
- `/reset` — konuşma hafızasını temizle
- `/exit` — çıkış

## iPhone'da (iOS) kullanım

Zenith native bir App Store uygulaması değil (bunun için Xcode + Apple
Developer hesabı gerekir); bunun yerine gerçek bir uygulama gibi davranan bir
**PWA (Progressive Web App)** olarak geliyor — Safari üzerinden telefonuna
kurup ana ekranından açabilirsin, tam ekran çalışır, kendi ikonu olur.

1. Sunucuyu başlat:

   ```bash
   python -m zenith web
   ```

   Varsayılan olarak `http://0.0.0.0:8000` adresinde çalışır.

2. iPhone'un bilgisayarla aynı Wi-Fi ağında olduğundan emin ol, bilgisayarının
   yerel IP'sini öğren (`ifconfig` / `ipconfig` — örn. `192.168.1.20`) ve
   iPhone'da Safari'den `http://192.168.1.20:8000` adresini aç.

   - Evden uzaktayken de erişmek istersen [Tailscale](https://tailscale.com)
     (ücretsiz) ile telefonunu ve bilgisayarını aynı özel ağa alabilir ya da
     Zenith'i Render/Fly.io/Railway gibi ücretsiz katmanı olan bir servise
     deploy edebilirsin.

3. Safari'de sayfa açıkken **Paylaş (Share) → Ana Ekrana Ekle**'ye dokun.
   Zenith artık telefonunda kendi ikonuyla, adres çubuğu olmadan, tam ekran
   açılan bir uygulama gibi durur.

Bu arayüz `/council` moduna karşılık gelen bir anahtar (Konsey modu),
hafızayı sıfırlama ve model durumunu listeleme butonları içerir — CLI'daki
tüm komutların mobil karşılığıdır.

## İnternete deploy etmek (telefondan her yerden erişim)

Ev ağı dışından da kullanmak istersen iki hazır yol var:

**Vercel (ücretsiz):** Repo'da `vercel.json` + `api/index.py` hazır.
Vercel hesabını GitHub'a bağlayıp bu repo'yu import etmen yeterli. Deploy
sonrası Vercel panelinden **Settings → Environment Variables** kısmına en az
bir ücretsiz API anahtarı ekle (örn. `GROQ_API_KEY`) — serverless ortamda
yerel Ollama olmadığı için anahtar şart. Hafıza serverless'ta geçicidir
(cold start'ta sıfırlanır).

**Docker (Render / Fly.io / Railway):** Repo'daki `Dockerfile` ile herhangi
bir container hostunda kalıcı hafızayla çalışır:

```bash
docker build -t zenith .
docker run -p 8000:8000 --env-file .env zenith
```

Deploy ettikten sonra çıkan `https://...` adresini iPhone'da Safari ile açıp
**Paylaş → Ana Ekrana Ekle** demen yeterli.

## Yeni bir ücretsiz model eklemek

`config/models.yaml` dosyasına yeni bir giriş eklemen yeterli:

```yaml
- name: benim-yeni-modelim
  litellm_id: groq/llama-3.1-70b-versatile
  provider: groq
  requires_key: GROQ_API_KEY
  tags: [chat, reasoning]
  priority: 1
```

`litellm_id` formatı için [LiteLLM sağlayıcı
dökümantasyonuna](https://docs.litellm.ai/docs/providers) bakabilirsin.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

Testler gerçek API çağrısı yapmaz; sağlayıcı katmanı mock'lanarak router ve
konsey mantığı (fallback, paralel sorgulama, sentez) izole şekilde test
edilir.

## Yol haritası fikirleri

- Fonksiyon çağırma / araç kullanımı (web arama, dosya okuma) için ortak bir
  şema katmanı
- Sesli komut (wake word) desteği, konuşma-to-metir girişi (iOS'ta Safari'nin
  yerleşik dikte özelliği zaten klavyeden çalışır)
- Yanıtları kelime kelime akıtan (streaming/SSE) sohbet arayüzü
- Uzun süreli hafıza (kullanıcı hakkında kalıcı bilgi/tercihler)
- Push notification (örn. hatırlatıcılar) için Web Push desteği
