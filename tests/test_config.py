import os

from zenith.config import load_config


def test_load_config_reads_all_models():
    config = load_config()
    assert len(config.models) > 0
    names = {m.name for m in config.models}
    assert "ollama-llama3.1-8b" in names


def test_ollama_models_always_available(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("ZENITH_DISABLE_OLLAMA", raising=False)
    config = load_config()
    ollama_models = [m for m in config.models if m.provider == "ollama"]
    assert ollama_models
    assert all(m.is_available() for m in ollama_models)


def test_ollama_disabled_in_serverless_env(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    config = load_config()
    ollama_models = [m for m in config.models if m.provider == "ollama"]
    assert all(not m.is_available() for m in ollama_models)


def test_ollama_disabled_via_flag(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("ZENITH_DISABLE_OLLAMA", "1")
    config = load_config()
    ollama_models = [m for m in config.models if m.provider == "ollama"]
    assert all(not m.is_available() for m in ollama_models)


def test_key_gated_model_unavailable_without_env(monkeypatch):
    config = load_config()
    groq = next(m for m in config.models if m.provider == "groq")
    monkeypatch.delenv(groq.requires_key, raising=False)
    assert groq.is_available() is False


def test_key_gated_model_available_with_env(monkeypatch):
    config = load_config()
    groq = next(m for m in config.models if m.provider == "groq")
    monkeypatch.setenv(groq.requires_key, "fake-key")
    assert groq.is_available() is True


def test_models_for_tags_falls_back_to_all_when_no_tag_match(monkeypatch):
    config = load_config()
    for m in config.models:
        if m.requires_key:
            monkeypatch.setenv(m.requires_key, "fake-key")
    result = config.models_for_tags(("nonexistent-tag",))
    assert result == config.available_models()
