# Zenith Yol Haritası

Zenith'in nereye gittiğini gösteren canlı bir plan. Kutular tamamlananları
işaretler.

## Faz 1 — Çekirdek (tamamlandı)
- [x] LiteLLM üzerinden çok sağlayıcılı model katmanı
- [x] Öncelik sıralı fallback zinciri (tek model modu)
- [x] Konsey modu (paralel modeller + sentez)
- [x] Kalıcı konuşma hafızası
- [x] Yerel araçlar (hesap makinesi, saat)
- [x] Terminal arayüzü (CLI)

## Faz 2 — Erişim & platform (tamamlandı)
- [x] FastAPI web/API katmanı
- [x] Mobil uyumlu, iOS-hazır PWA (Ana Ekrana Ekle)
- [x] Vercel + Docker dağıtımı
- [x] 26 ücretsiz/açık kaynak model (Hermes 3 405B, DeepSeek, Llama 4...)
- [x] GitHub Models sağlayıcısı

## Faz 3 — Yetenekler (tamamlandı)
- [x] Ücretsiz web araması (`ara:`)
- [x] Wikipedia (`wiki:`)
- [x] Hava durumu (`hava:`)
- [x] Döviz kuru (`kur:`)
- [x] Sayfa özetleme (`ozetle:`)
- [x] Sherlock tarzı kullanıcı adı arama (`kullanici:`)
- [x] Haber başlıkları (`haber:`)
- [x] İngilizce sözlük (`sozluk:`)
- [x] Şifre üretici (`sifre:`)
- [x] Kalıcı notlar/hatırlatıcılar (`not:`, `notlarim`)

## Faz 4 — Deneyim (tamamlandı)
- [x] Canlı akan cevaplar (streaming / SSE)
- [x] Markdown görüntüleme + kopyala butonu
- [x] Model seçici, konsey anahtarı
- [x] Hoş geldin ekranı + öneri çipleri
- [x] Sesli okuma (TTS) + mikrofonla giriş
- [x] Kalıcı geçmiş + sohbet dışa aktarma
- [x] Açık/koyu tema

## Faz 5 — Gelişmiş deneyim (tamamlandı)
- [x] Çoklu sohbet oturumları (kenar çubuğu, oturumlar arası geçiş)
- [x] Görsel yükleme + vision modelleriyle analiz
- [x] Sesli konuşma modu (eller-serbest, kesintisiz döngü)

## Faz 6 — Sıradaki fikirler (planlanıyor)
- [ ] Gerçek fonksiyon çağırma (function calling) katmanı
- [ ] Uzun süreli hafıza (kullanıcı tercihleri/profili)
- [ ] Web Push ile hatırlatıcı bildirimleri
- [ ] Kod çalıştırma (güvenli sandbox)
- [ ] RAG: kendi belgelerinle sohbet

Bir fikrin mi var? `config/models.yaml` ve `zenith/skills.py` en kolay
genişletme noktalarıdır.
