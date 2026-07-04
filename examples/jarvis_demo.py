"""Zenith Jarvis Demo - Tüm özelliklerinin gösterimi."""

import asyncio
from zenith.assistant import ZenithAssistant
from zenith.voice_interface import VoiceInterface, VoiceConfig
from zenith.smart_home import SmartHomeHub, SmartDevice, DeviceType
from zenith.jarvis_integrations import JarvisIntegration
from zenith.advanced_reasoning import AdvancedReasoner, ReasoningType
from zenith.memory_system import MemorySystem


async def demo_basic_chat():
    """Basit sohbet demo."""
    print("\n🤖 Zenith Jarvis - Temel Chat Demo\n")
    assistant = ZenithAssistant()
    
    questions = [
        "Merhaba! Adın ne?",
        "Bugün hava nasıl?",
        "Python'da async nedir?",
    ]
    
    for q in questions:
        print(f"User: {q}")
        result = await assistant.ask(q)
        print(f"Zenith: {result.text}\n")


async def demo_jarvis_models():
    """Jarvis modellerini göster."""
    print("\n📊 Zenith Jarvis Models Demo\n")
    integration = JarvisIntegration()
    
    # Tüm modelleri listele
    print("📋 Desteklenen Jarvis Modelleri:\n")
    for model in integration.list_available():
        print(f"✨ {model['name']}")
        print(f"   ⭐ Stars: {model['stars']}")
        print(f"   📝 {model['description']}")
        print(f"   🏷️  Tags: {', '.join(model['features'])}")
        print()
    
    # Python modelleri öner
    print("\n🐍 Python Tabanlı Jarvis'ler:\n")
    python_models = integration.recommend_models(features=["voice", "local"], language="Python")
    for model in python_models:
        print(f"  ✓ {model.name} ({model.stars} ⭐)")


async def demo_voice():
    """Ses arayüzü demo."""
    print("\n🎤 Voice Interface Demo\n")
    
    config = VoiceConfig(
        language="tr-TR",
        voice_gender="female",
        voice_speed=1.0,
    )
    
    voice = VoiceInterface(config)
    print(f"✓ Ses konfigürasyonu hazırlandı")
    print(f"  Language: {config.language}")
    print(f"  Voice: {config.voice_gender}")
    print(f"  STT Engine: {config.stt_engine}")
    print(f"  TTS Engine: {config.tts_engine}")


async def demo_smart_home():
    """Akıllı ev demo."""
    print("\n🏠 Smart Home Demo\n")
    
    hub = SmartHomeHub()
    
    # Cihazları ekle
    devices = [
        SmartDevice("living_room_light", "Salon Işığı", DeviceType.LIGHT, False),
        SmartDevice("bedroom_light", "Yatak Odası Işığı", DeviceType.LIGHT, False),
        SmartDevice("thermostat", "Termostat", DeviceType.THERMOSTAT, 20),
        SmartDevice("front_door", "Ön Kapı", DeviceType.LOCK, False),
    ]
    
    for device in devices:
        hub.add_device(device)
    
    print("📱 Akıllı cihazlar:")
    for dev in hub.list_devices():
        print(f"  ✓ {dev['name']} ({dev['type']}) - State: {dev['state']}")
    
    # Kontrol et
    print("\n⚡ Cihazları kontrol et:")
    await hub.control_device("living_room_light", "turn_on")
    print("  ✓ Salon ışığı açıldı")
    
    await hub.control_device("thermostat", "set_value", 22)
    print("  ✓ Termostat 22°C'ye ayarlandı")


async def demo_advanced_reasoning():
    """İleri muhakeme demo."""
    print("\n🧠 Advanced Reasoning Demo\n")
    
    reasoner = AdvancedReasoner()
    
    problem = "Bir mağazada 3 kırmızı ve 5 mavi top var. 2 top çıkarılırsa, en az 1'inin kırmızı olma ihtimali nedir?"
    print(f"Problem: {problem}\n")
    
    reasoning = await reasoner.solve(problem, ReasoningType.CHAIN_OF_THOUGHT)
    print(reasoning)


async def demo_memory():
    """Hafıza sistemi demo."""
    print("\n🧠 Memory System Demo\n")
    
    memory = MemorySystem()
    
    # Hafıza ekle
    print("Hafızalara bilgiler ekleniyor...\n")
    
    mem1 = memory.add_memory(
        "Kullanıcının adı Ali. Python'u seviyor ve YSA ile ilgileniyor.",
        category="personal",
        importance=0.9,
        tags=["kullanıcı", "isim", "ilgi"]
    )
    print(f"✓ Hafıza 1 eklendi: {mem1}")
    
    mem2 = memory.add_memory(
        "Ali'nin favori yemeği mantı.",
        category="preference",
        importance=0.7,
        tags=["yemek", "tercih"]
    )
    print(f"✓ Hafıza 2 eklendi: {mem2}")
    
    # Hafızayı geri çağır
    print("\n📚 Hafızayı sorgulamak:")
    results = memory.recall_memory("Ali")
    for mem in results:
        print(f"  ✓ [{mem.category}] {mem.content}")
    
    # Özet
    print("\n📊 Hafıza Özeti:")
    summary = memory.get_memory_summary()
    print(f"  Toplam hafızalar: {summary['total_memories']}")
    print(f"  Kategoriler: {summary['by_category']}")
    print(f"  Ortalama önem: {summary['average_importance']:.2f}")


async def demo_council_mode():
    """Council mode demo."""
    print("\n👥 Council Mode (Konsey Modu) Demo\n")
    print("Konsey modu: Birden fazla AI modeli aynı soruya cevap verir.")
    print("Sonra bir 'sentezleyici' model bu cevapları birleştirir.\n")
    
    assistant = ZenithAssistant()
    assistant.council_mode = True
    
    question = "Yapay zeka nedir?"
    print(f"Soru: {question}\n")
    
    result = await assistant.ask(question)
    print(f"Zenith (Konsey): {result.text}")
    if result.contributors:
        print(f"Katkıda bulunanlar: {', '.join(result.contributors)}")


async def main():
    """Tüm demolar."""
    print("" "  🤖 ZENITH JARVIS - COMPREHENSIVE DEMO 🤖")
    print("" "=" * 50)
    
    # Demo'lar
    await demo_jarvis_models()
    # await demo_basic_chat()  # API key gerekli
    await demo_voice()
    await demo_smart_home()
    await demo_advanced_reasoning()
    await demo_memory()
    # await demo_council_mode()  # API key gerekli
    
    print("\n" + "=" * 50)
    print("✨ Demo tamamlandı!\n")


if __name__ == "__main__":
    asyncio.run(main())
