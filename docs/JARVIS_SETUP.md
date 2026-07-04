# 🤖 Zenith Jarvis Kurulum Rehberi

Zenith'i **Iron Man tarzı bir Jarvis asistanı** olarak kurmak için adım adım rehber.

## 📋 Gereksinimler

- **Python 3.10+**
- **pip** veya **poetry**
- **Git** (klonlama için)
- **GPU** (isteğe bağlı, daha hızlı işlem için)

## 🚀 Hızlı Başlangıç (5 dakika)

### 1. Zenith'i Kur

```bash
# Repository'yi klonla
git clone https://github.com/gyh52ckbw5-creator/Zenith
cd Zenith

# Sanal ortam oluştur
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 2. API Anahtarlarını Ayarla

```bash
# .env dosyasını oluştur
cp .env.example .env

# Editörle aç ve API anahtarlarını ekle
# En az birini kullan:
# - OPENROUTER_API_KEY (önerilen, 50+ free model)
# - GITHUB_API_KEY (GitHub hesapına varsa)
# - GEMINI_API_KEY
```

### 3. Jarvis Modellerini Seç

```bash
# CLI başlat
python -m zenith

# Komutlar:
# /models          - Tüm modelleri listele
# /models list     - Desteklenen Jarvis'leri gör
# Soru sor         - Normal chat
```

## 📱 Web Arayüzü Başlat (PWA)

```bash
python -m zenith web

# Tarayıcıda aç: http://localhost:8000
# iPhone'da: "Ana Ekrana Ekle"
```

## 🎤 Ses Desteği Ekle

Tüm Jarvis modellerinin ses desteği için:

```bash
pip install[voice]:
- google-cloud-speech
- gtts
- pyaudio
- sounddevice
```

Sonra:

```python
from zenith.voice_interface import VoiceInterface, VoiceConfig

config = VoiceConfig(
    language="tr-TR",      # Türkçe
    voice_gender="female", # Kadın sesi
    enable_stt=True,      # Dinleme
    enable_tts=True,      # Konuşma
)

voice = VoiceInterface(config)

# Dinle
text = await voice.listen()

# Konuş
await voice.speak("Merhaba!")
```

## 🏠 Akıllı Ev Otomasyonu

### Home Assistant Entegrasyonu

```bash
pip install homeassistant
```

```python
from zenith.smart_home import SmartHomeHub, SmartDevice, DeviceType

hub = SmartHomeHub()

# Cihaz ekle
light = SmartDevice(
    id="living_room_light",
    name="Salon Işığı",
    device_type=DeviceType.LIGHT,
    state=False,
)
hub.add_device(light)

# Kontrol et
await hub.control_device("living_room_light", "turn_on")
```

## 🤖 Farklı Jarvis Modellerini Kullan

### OpenJarvis

```bash
git clone https://github.com/open-jarvis/OpenJarvis
cd OpenJarvis
pip install -r requirements.txt
python main.py
```

### Leon

```bash
git clone https://github.com/leon-ai/leon
cd leon
npm install
npm start
```

### Mycroft

```bash
pip install mycroft-core
mycroft-start
```

## 🔧 Zenith'i Jarvis Gibi Ayarla

### System Prompt Özelleştir

```bash
# .env'de
ZENITH_SYSTEM_PROMPT="
Sen Zenith, Tony Stark'ın AI asistanı Jarvis gibi bir kişilik sahibi misin.
Profesyonel, yardımcı, ve biraz tatlı. İronik yorum yapabilirsin.
Her zaman Türkçe konuş.
"
```

### CLI Komutları

Zenith'e kişisel komutlar ekle (`zenith/skills.py`'de):

```python
async def power_down(duration: str) -> str:
    """Sistem belirtilen süre sonra kapatılacak."""
    return f"Sistem {duration} sonra kapatılacak."
```

## 📊 Analitikleri Kontrol Et

```bash
python -m zenith
/analytics  # İstatistikleri gör
```

## 🔐 Güvenlik Ayarları

```python
# .env
ZENITH_CACHE_TTL=24           # Yanıt cache süresi (saat)
ZENITH_MAX_CONCURRENT=5       # Max eş zamanlı istek
ZENITH_LOG_LEVEL=INFO         # Log seviyesi
ZENITH_DISABLE_OLLAMA=false   # Ollama kapat
```

## 💻 Masaüstü Uygulaması

### PyQt ile GUI

```bash
pip install PyQt6
```

```python
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit
from zenith.server import app

class ZenithApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        self.chat = QTextEdit()
        self.setCentralWidget(self.chat)
        self.show()

if __name__ == "__main__":
    import sys
    app_qt = QApplication(sys.argv)
    zenith = ZenithApp()
    sys.exit(app_qt.exec())
```

## 🌐 Vercel'de Deploy

```bash
# 1. Vercel hesabı oluştur (vercel.com)
# 2. Project'i bağla
vercel

# 3. Environment variables ekle (Vercel dashboard)
# OPENROUTER_API_KEY=...
# GITHUB_API_KEY=...

# 4. Deploy
vercel deploy
```

## 🧪 Testler

```bash
# Tüm testleri çalıştır
pytest

# Spesifik testler
pytest tests/test_cache.py -v
pytest tests/test_safety.py -v

# Coverage
pytest --cov=zenith
```

## 📚 Dökümantasyon

- [README.md](../README.md) - Genel bilgi
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Katkı rehberi
- [SECURITY.md](../SECURITY.md) - Güvenlik
- [JARVIS_MODELS.md](../JARVIS_MODELS.md) - Tüm desteklenen modeller

## 🆘 Sorun Giderme

### "API key not found"
```bash
# .env dosyasını kontrol et
cat .env

# En az bir API key gerekli
echo "OPENROUTER_API_KEY=your_key" >> .env
```

### "No available models"
```bash
# Kullanılabilir modelleri kontrol et
python -c "from zenith.config import load_config; c = load_config(); print([m.name for m in c.available_models()])"
```

### Ses çalışmıyor
```bash
# PyAudio kur
pip install pyaudio

# Linux'ta:
sudo apt-get install portaudio19-dev
```

## 🎯 Sonraki Adımlar

1. **Özel Skills Ekle** - `zenith/skills.py`'de
2. **Jarvis Modellerini Entegre Et** - `zenith/jarvis_integrations.py`'de
3. **GitHub'da Yayınla** - Başkalarına yardım et!

---

**Başarılar! Jarvis'in Türkçe sürümünü yaratmışsın!** 🚀
