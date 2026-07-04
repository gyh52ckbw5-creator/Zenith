"""Açık kaynak Jarvis modellerinin entegrasyonu.

En popüler açık kaynak AI assistant projelerini Zenith'e entegre eder:
- OpenJarvis, Leon, Mycroft, Kalliope, Rhasspy, vb.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import os
from pathlib import Path


@dataclass
class JarvisModel:
    """Bir Jarvis AI assistant modeli."""

    name: str
    repo_url: str
    description: str
    features: list[str]
    language: str
    stars: int
    github_id: str
    license: str
    enabled: bool = False
    config: dict[str, Any] | None = None


class JarvisIntegration:
    """Tüm açık kaynak Jarvis modellerini yönet."""

    # En popüler ve iyi maintain edilen Jarvis projeleri
    AVAILABLE_MODELS = [
        JarvisModel(
            name="OpenJarvis",
            repo_url="https://github.com/open-jarvis/OpenJarvis",
            description="Iron Man tarzı açık kaynak kişisel AI asistan. Lokal çalışır, ses desteği, web tarama, müzik oynatma.",
            features=["voice", "local", "privacy", "web-browsing", "music", "automation"],
            language="Python",
            stars=8200,
            github_id="open-jarvis/OpenJarvis",
            license="MIT",
        ),
        JarvisModel(
            name="Leon",
            repo_url="https://github.com/leon-ai/leon",
            description="Modüler, gizlilik odaklı kişisel asistan. JavaScript tabanlı, masaüstü ve sunucu desteği.",
            features=["voice", "local", "privacy", "modular", "automation", "node-based"],
            language="JavaScript/TypeScript",
            stars=14300,
            github_id="leon-ai/leon",
            license="Apache-2.0",
        ),
        JarvisModel(
            name="Mycroft AI",
            repo_url="https://github.com/MycroftAI/mycroft-core",
            description="En ünlü açık kaynak ses asistanı. Raspberry Pi, Linux, Cloud desteği.",
            features=["voice", "local", "privacy", "skills", "smart-home", "cross-platform"],
            language="Python",
            stars=7100,
            github_id="MycroftAI/mycroft-core",
            license="Apache-2.0",
        ),
        JarvisModel(
            name="Kalliope",
            repo_url="https://github.com/kalliope-project/kalliope",
            description="Modüler, Python tabanlı ses asistanı. Raspberry Pi için optimize edilmiş.",
            features=["voice", "local", "modular", "raspberry-pi", "privacy", "neurons"],
            language="Python",
            stars=3500,
            github_id="kalliope-project/kalliope",
            license="GPL-3.0",
        ),
        JarvisModel(
            name="Rhasspy",
            repo_url="https://github.com/rhasspy/rhasspy",
            description="Ses asistan araç seti. Home Assistant, ev otomasyonu entegrasyonu.",
            features=["voice", "local", "smart-home", "privacy", "home-assistant", "offline"],
            language="Python",
            stars=4200,
            github_id="rhasspy/rhasspy",
            license="MIT",
        ),
        JarvisModel(
            name="Jarvis-Desktop-Voice-Assistant",
            repo_url="https://github.com/kishanrajput23/Jarvis-Desktop-Voice-Assistant",
            description="Python tabanlı masaüstü ses asistanı. Sistem komutları, TTS/STT entegrasyonu.",
            features=["voice", "desktop", "system-commands", "tts", "stt", "local"],
            language="Python",
            stars=2100,
            github_id="kishanrajput23/Jarvis-Desktop-Voice-Assistant",
            license="MIT",
        ),
        JarvisModel(
            name="JARVIS-ChatGPT",
            repo_url="https://github.com/gia-guar/JARVIS-ChatGPT",
            description="ChatGPT + Watson entegre yapay Jarvis sesi ile konuşan asistan.",
            features=["voice", "chatgpt", "watson", "conversation", "tts"],
            language="Python",
            stars=1800,
            github_id="gia-guar/JARVIS-ChatGPT",
            license="MIT",
        ),
        JarvisModel(
            name="Almond (Stanford OVAL)",
            repo_url="https://github.com/stanford-oval/genie",
            description="Stanford'dan gizlilik odaklı sanal asistan. Kendi makinende çalışır.",
            features=["privacy", "local", "smart-home", "nlp", "composable"],
            language="JavaScript/TypeScript",
            stars=2800,
            github_id="stanford-oval/genie",
            license="Apache-2.0",
        ),
        JarvisModel(
            name="Project Alice",
            repo_url="https://github.com/project-alice-assistant/ProjectAlice",
            description="Genişletilebilir, modüler asistan. Ses ve akıllı ev entegrasyonu.",
            features=["voice", "modular", "smart-home", "local", "customizable"],
            language="Python",
            stars=2400,
            github_id="project-alice-assistant/ProjectAlice",
            license="GPL-3.0",
        ),
        JarvisModel(
            name="Bitterbot",
            repo_url="https://github.com/Bitterbot-AI/bitterbot-desktop",
            description="Lokal-first, çok platformlu AI asistan. Kalıcı hafıza, duygusal zeka.",
            features=["local", "multi-platform", "memory", "emotional-ai", "p2p-skills"],
            language="Python",
            stars=1200,
            github_id="Bitterbot-AI/bitterbot-desktop",
            license="MIT",
        ),
        JarvisModel(
            name="Friday",
            repo_url="https://github.com/thesongzhu/Friday",
            description="Yüksek modüler, gizlilik kontrol düzlemi. İş akışı otomasyonu, mobil app desteği.",
            features=["modular", "privacy", "automation", "mobile", "workflow", "ai-agents"],
            language="Python",
            stars=3600,
            github_id="thesongzhu/Friday",
            license="MIT",
        ),
    ]

    def __init__(self):
        self.models = {m.github_id: m for m in self.AVAILABLE_MODELS}
        self.enabled_models: dict[str, JarvisModel] = {}

    def enable_model(self, github_id: str, config: dict[str, Any] | None = None) -> bool:
        """Bir Jarvis modelini etkinleştir."""
        if github_id not in self.models:
            return False
        model = self.models[github_id]
        model.enabled = True
        model.config = config or {}
        self.enabled_models[github_id] = model
        return True

    def disable_model(self, github_id: str) -> bool:
        """Bir Jarvis modelini devre dışı bırak."""
        if github_id not in self.enabled_models:
            return False
        self.models[github_id].enabled = False
        del self.enabled_models[github_id]
        return True

    def list_available(self) -> list[dict[str, Any]]:
        """Tüm mevcut modelleri listele."""
        return [
            {
                "name": m.name,
                "repo": m.repo_url,
                "description": m.description,
                "features": m.features,
                "language": m.language,
                "stars": m.stars,
                "license": m.license,
                "enabled": m.enabled,
            }
            for m in self.AVAILABLE_MODELS
        ]

    def list_enabled(self) -> list[dict[str, Any]]:
        """Etkinleştirilmiş modelleri listele."""
        return [
            {
                "name": m.name,
                "repo": m.repo_url,
                "features": m.features,
                "config": m.config,
            }
            for m in self.enabled_models.values()
        ]

    def get_model(self, github_id: str) -> JarvisModel | None:
        """Belirli bir modeli al."""
        return self.models.get(github_id)

    def search_by_feature(self, feature: str) -> list[JarvisModel]:
        """Belirli bir özelliğe göre modelleri ara."""
        return [m for m in self.AVAILABLE_MODELS if feature in m.features]

    def recommend_models(self, features: list[str], language: str | None = None) -> list[JarvisModel]:
        """İstenen özellik ve dile göre modelleri öner."""
        matches = [m for m in self.AVAILABLE_MODELS
                   if all(f in m.features for f in features)]
        if language:
            matches = [m for m in matches if language.lower() in m.language.lower()]
        return sorted(matches, key=lambda m: m.stars, reverse=True)

    def to_json(self) -> str:
        """Tüm modelleri JSON olarak dışa aktar."""
        return json.dumps(
            [{
                "name": m.name,
                "repo": m.repo_url,
                "description": m.description,
                "features": m.features,
                "language": m.language,
                "stars": m.stars,
                "license": m.license,
            } for m in self.AVAILABLE_MODELS],
            ensure_ascii=False,
            indent=2,
        )
