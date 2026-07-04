"""Ses arayüzü ve multi-modal input/output.

Tüm Jarvis modellerinin ses, video ve metin desteklemesi için ortak arayüz.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Optional


class InputMode(Enum):
    """Giriş modu."""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"
    COMMAND = "command"


class OutputMode(Enum):
    """Çıkış modu."""
    TEXT = "text"
    VOICE = "voice"
    VISUAL = "visual"
    ACTION = "action"
    STREAM = "stream"


@dataclass
class VoiceConfig:
    """Ses yapılandırması."""
    language: str = "tr-TR"  # Türkçe varsayılan
    voice_gender: str = "female"  # "male", "female", "neutral"
    voice_speed: float = 1.0  # 0.5 - 2.0
    voice_pitch: float = 1.0  # 0.5 - 2.0
    enable_stt: bool = True  # Speech-to-Text
    enable_tts: bool = True  # Text-to-Speech
    stt_engine: str = "google"  # "google", "deepgram", "whisper"
    tts_engine: str = "gtts"  # "gtts", "elevenlabs", "azure"
    wake_word: str = "hey jarvis"  # Uyanma sözcüğü
    noise_suppression: bool = True
    echo_cancellation: bool = True


class VoiceInterface:
    """Ses giriş/çıkışını yönet."""

    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig()
        self.is_listening = False
        self.is_speaking = False

    async def listen(self, timeout: float = 10.0) -> str | None:
        """Kullanıcının sesini dinle ve metne çevir."""
        self.is_listening = True
        try:
            # STT motoru seçimlerine göre dinleme yap
            if self.config.stt_engine == "whisper":
                text = await self._whisper_stt(timeout)
            else:
                text = await self._google_stt(timeout)
            return text
        finally:
            self.is_listening = False

    async def speak(self, text: str, streaming: bool = False) -> None | AsyncIterator[bytes]:
        """Metni sese çevir ve oynat (veya akış olarak döndür)."""
        self.is_speaking = True
        try:
            if self.config.tts_engine == "elevenlabs":
                return await self._elevenlabs_tts(text, streaming)
            else:
                return await self._gtts_tts(text, streaming)
        finally:
            self.is_speaking = False

    async def _whisper_stt(self, timeout: float) -> str | None:
        """OpenAI Whisper STT."""
        try:
            import openai
            # Audio record ve transcribe
            # Bu basitleştirilmiş sürüm; gerçek implementasyon daha karmaşık
            return "[Whisper STT çıkışı]"
        except ImportError:
            return None

    async def _google_stt(self, timeout: float) -> str | None:
        """Google Cloud STT."""
        try:
            from google.cloud import speech
            # Google STT implementasyonu
            return "[Google STT çıkışı]"
        except ImportError:
            return None

    async def _elevenlabs_tts(self, text: str, streaming: bool) -> bytes | AsyncIterator[bytes]:
        """ElevenLabs TTS."""
        try:
            import elevenlabs
            # ElevenLabs TTS implementasyonu
            return b"[ElevenLabs TTS çıkışı]"
        except ImportError:
            return b""

    async def _gtts_tts(self, text: str, streaming: bool) -> bytes:
        """Google Text-to-Speech (gTTS)."""
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang="tr", slow=False)
            # Audio byte'larını döndür
            import io
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            return fp.read()
        except ImportError:
            return b""

    def is_listening_now(self) -> bool:
        """Şu anda dinliyor mu?"""
        return self.is_listening

    def is_speaking_now(self) -> bool:
        """Şu anda konuşuyor mu?"""
        return self.is_speaking


class MultiModalInterface:
    """Çok modlu giriş/çıkış (ses, görüntü, metin)."""

    def __init__(self, voice_config: VoiceConfig | None = None):
        self.voice = VoiceInterface(voice_config)
        self.input_mode = InputMode.TEXT
        self.output_mode = OutputMode.TEXT

    async def process_input(self, data: str | bytes, mode: InputMode) -> str:
        """Giriş verilerini işle ve metne çevir."""
        if mode == InputMode.TEXT:
            return data.decode() if isinstance(data, bytes) else data
        elif mode == InputMode.VOICE:
            # Ses dosyasını metne çevir
            return await self._process_voice(data)
        elif mode == InputMode.IMAGE:
            # Görüntüyü metne çevir (OCR/Vision)
            return await self._process_image(data)
        elif mode == InputMode.COMMAND:
            # Sistem komutu
            return await self._process_command(data)
        return ""

    async def process_output(self, text: str, mode: OutputMode) -> bytes | str | None:
        """Çıkış modu seçip hazırla."""
        if mode == OutputMode.TEXT:
            return text
        elif mode == OutputMode.VOICE:
            return await self.voice.speak(text)
        elif mode == OutputMode.STREAM:
            return await self.voice.speak(text, streaming=True)
        elif mode == OutputMode.ACTION:
            # Sistem aksionu (dosya açma, ayar değiştirme vb.)
            return await self._execute_action(text)
        return None

    async def _process_voice(self, audio: bytes) -> str:
        """Ses verilerini metne çevir."""
        return "[Ses metne çevrildi]"

    async def _process_image(self, image: bytes) -> str:
        """Görüntüyü metne çevir."""
        return "[Görüntü metne çevrildi]"

    async def _process_command(self, command: str) -> str:
        """Sistem komutunu işle."""
        return f"Komut işleniyor: {command}"

    async def _execute_action(self, action: str) -> str:
        """Aksiyonu çalıştır."""
        return f"Aksiyon çalıştırılıyor: {action}"
