"""Jarvis entegrasyon testleri."""

from __future__ import annotations

import pytest
from zenith.jarvis_integrations import JarvisIntegration, JarvisModel


def test_jarvis_integration_init():
    """Jarvis entegrasyonu başlatma."""
    integration = JarvisIntegration()
    assert len(integration.AVAILABLE_MODELS) > 0
    assert integration.AVAILABLE_MODELS[0].name == "OpenJarvis"


def test_list_available_models():
    """Mevcut modelleri listele."""
    integration = JarvisIntegration()
    models = integration.list_available()
    assert len(models) > 0
    assert all("name" in m for m in models)
    assert all("repo" in m for m in models)


def test_enable_model():
    """Modeli etkinleştir."""
    integration = JarvisIntegration()
    result = integration.enable_model("open-jarvis/OpenJarvis")
    assert result is True
    assert len(integration.enabled_models) > 0


def test_disable_model():
    """Modeli devre dışı bırak."""
    integration = JarvisIntegration()
    integration.enable_model("open-jarvis/OpenJarvis")
    result = integration.disable_model("open-jarvis/OpenJarvis")
    assert result is True
    assert len(integration.enabled_models) == 0


def test_search_by_feature():
    """Özelliğe göre ara."""
    integration = JarvisIntegration()
    voice_models = integration.search_by_feature("voice")
    assert len(voice_models) > 0
    assert all("voice" in m.features for m in voice_models)


def test_recommend_models():
    """Modelleri öner."""
    integration = JarvisIntegration()
    recommendations = integration.recommend_models(
        features=["voice", "local"],
        language="Python"
    )
    assert len(recommendations) > 0
    assert all("voice" in m.features for m in recommendations)
    assert all("local" in m.features for m in recommendations)
