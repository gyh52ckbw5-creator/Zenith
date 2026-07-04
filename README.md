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
- **Yetenekler (skills)**: Anahtarsız, ücretsiz servislerle çalışan komutlar.
  Bir soru sorar gibi yazarsın, Zenith doğru aracı kendi seçer:

  | Komut | Ne yapar | Örnek |
  |---|---|---|
  | `ara:` | DuckDuckGo'da arar, bulguları modele verip kaynaklı cevap ürettirir | `ara: bugün dolar kuru` |
  | `wiki:` | Wikipedia özeti getirir | `wiki: kuantum fiziği` |
  | `hava:` | Anlık hava durumu (open-meteo) | `hava: İstanbul` |
  | `kur:` | Döviz kuru çevirir (frankfurter) | `kur: 100 dolar tl` |
  | `haber:` | Güncel haber başlıkları (Google News) | `haber: ekonomi` |
  | `sozluk:` | İngilizce sözlük tanımı | `sozluk: serendipity` |
  | `sifre:` | Güvenli rastgele şifre üretir (yerel) | `sifre: 20` |
  | `ozetle:` | Bir web sayfasını getirip özetletir | `ozetle: https://...` |
  | `kullanici:` | Sherlock tarzı: bir kullanıcı adını popüler sitelerde arar | `kullanici: torvalds` |
  | `not:` / `notlarim` | Kalıcı notlar/hatırlatıcılar (ekle, listele, `not sil 1`) | `not: yarın faturayı öde` |
  | `hesapla:` | Yerel hesap makinesi | `hesapla: 12*7` |
- **Sesli kullanım (web arayüzü)**: "Sesli oku" anahtarı cevapları Türkçe
  seslendirir; destekleyen tarayıcılarda mikrofon butonuyla konuşarak
  yazdırabilirsin (iOS'ta klavyedeki dikte tuşu da her zaman çalışır).
- **Canlı akan cevaplar (streaming)**: Cevaplar Jarvis gibi kelime kelime
  yazılır (Server-Sent Events). Bir model akışın başında çökerse otomatik
  olarak sıradaki modele geçilir. (Yerel/Docker kurulumda anlık akar;
  bazı serverless platformlar yanıtı tamponlayıp tek seferde gösterebilir —
  işlevsel olarak aynıdır.)
- **Cilalı sohbet arayüzü** (Open WebUI / LibreChat / Lobe Chat'ten ilhamla):
  hoş geldin ekranı ve tek dokunuşla dolduran öneri çipleri, markdown
  görüntüleme (kod blokları, listeler, linkler), her cevapta kopyala butonu,
  üstteki seçiciden model seçimi ("Oto model" = öncelik zinciri), telefonda
  kalıcı geçmiş, "İndir" ile markdown dışa aktarma, açık/koyu tema. Enter ile
  gönder / Shift+Enter ile yeni satır. `/api/chat` (veya `/api/chat/stream`)
  gövdesindeki `system` alanıyla istek başına kişilik de değiştirilebilir.

## Mimari

```
zenith/
  config.py      # config/models.yaml içindeki model kaydını yükler
  providers.py    # LiteLLM üzerinden herhangi bir sağlayıcıyı çağıran ince katman
  router.py       # tek-model modu: öncelik sıralı fallback zinciri
  council.py      # konsey modu: paralel sorgu + sentez
  memory.py       # dosya tabanlı konuşma hafızası
  tools.py        # yerel, LLM'siz komutlar (hesap makinesi, saat)
  websearch.py    # ücretsiz DuckDuckGo web araması ("ara: <sorgu>")
  skills.py       # anahtarsız yetenekler (wiki, hava, kur, sayfa özet, kullanıcı arama)
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

| Sağlayıcı | Ücretsiz ne veriyor | Anahtar |
|---|---|---|
| **OpenRouter (önerilen)** | Tek anahtarla `:free` etiketli onlarca açık kaynak model: **Hermes 3 405B**, DeepSeek V3/R1, Llama 4, Qwen3, Kimi K2, GLM 4.5, gpt-oss... | https://openrouter.ai/keys |
| **GitHub Models** | GitHub hesabın zaten varsa ekstra kayıt yok: GPT-4o-mini, DeepSeek-R1, Llama 3.3, Phi-4 | https://github.com/settings/tokens (`models:read` izni) |
| Google Gemini | Gemini 2.0 Flash ücretsiz katman | https://aistudio.google.com/apikey |
| Mistral | Mistral Small ücretsiz deney katmanı | https://console.mistral.ai |
| Cerebras | Llama 70B, çok hızlı inference | https://cloud.cerebras.ai |
| Groq (isteğe bağlı) | Llama/DeepSeek modelleri | https://console.groq.com/keys |
| Ollama (yerel, sınırsız) | Hermes 3, Llama, Qwen, DeepSeek yerel çalışır | https://ollama.com — `ollama pull hermes3` |

Not: Sağlayıcıların ücretsiz model listeleri zamanla değişebilir;
`config/models.yaml` dosyasını kendi hesabına göre güncelleyebilirsin.
Zenith'in kişiliğini de `ZENITH_SYSTEM_PROMPT` ortam değişkeniyle
özelleştirebilirsin.

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
bir ücretsiz API anahtarı ekle (önerilen: `OPENROUTER_API_KEY`) — serverless
ortamda yerel Ollama olmadığı için anahtar şart. Hafıza serverless'ta
geçicidir (cold start'ta sıfırlanır).

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
