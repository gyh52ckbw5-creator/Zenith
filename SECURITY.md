# Güvenlik Politikası

## Güvenlik Açığı Bildirme

Zenith'te bir güvenlik açığı bulursan, **GitHub Issues'te açıkça paylaşma**. Bunun yerine:

1. `security@zenith-project.org` (yoksa en kıdemli maintainer) adresine email gönder
2. Açığın ayrıntılarını ve etki alanını açıkla
3. Düzeltme için zaman ver (genelde 90 gün)

## Güvenlik Uygulamaları

Zenith aşağıdakilerle tasarlanmıştır:

### 1. **Anahtarlar & Şifreler**
- API anahtarları `.env` dosyasında tutulur (repo'ya eklenmez)
- `python-jose` ve `passlib` ile şifreler hash'lenip saklanır
- Bellekte hassas bilgiler temizlenir

### 2. **Giriş Doğrulama**
- Tüm kullanıcı girdileri kontrol edilir
- Jailbreak ve spam desenleri algılanır
- Metin uzunluğu sınırlanır

### 3. **Çıktı Temizleme**
- Modellerin çıktıları zararlı içeriğe kontrol edilir
- HTML escape yapılır

### 4. **İletişim**
- Tüm API çağrıları HTTPS/TLS kullanır
- LiteLLM sertifikaları doğrular

### 5. **Bağımlılıklar**
- `pip` ve `pip-audit` ile düzenli kontrol
- `requirements.txt` sürümlendirilmiş
- Security updates otomatik izlenir

### 6. **Logging & Monitoring**
- Hassas bilgi log'a yazılmaz
- Anomali tespiti ve uyarılar
- Audit trails tutulur

## Düzeltilen Açıklar

Önceden düzeltilen güvenlik açıkları:

| Tarih | Açık | Durum |
|-------|------|-------|
| - | - | - |

## Best Practices

Zenith'i kullanırken:

1. **En son sürümü kullan** (`pip install --upgrade zenith`)
2. **API anahtarlarını paylaşma** (`.env` dosyasını gizli tut)
3. **Proxy/VPN arkasında kullan** (eğer gizlilik istiyorsan)
4. **Düzenli backup al** (memory.json, notes.json, vb.)

Sorular? security@zenith-project.org adresine yazabilir veya issue açabilirsin.
