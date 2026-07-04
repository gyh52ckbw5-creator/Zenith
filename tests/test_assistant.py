import pytest

from zenith import assistant as assistant_module
from zenith.assistant import ZenithAssistant
from zenith.config import ModelSpec, ZenithConfig
from zenith.memory import ConversationMemory
from zenith.providers import ModelReply
from zenith.websearch import SearchError, SearchResult


def make_assistant(tmp_path, council_mode=False) -> ZenithAssistant:
    config = ZenithConfig(
        models=(ModelSpec("m1", "p/m1", "p", None, ("reasoning",), priority=1),),
        council_max_parallel=4,
        synthesizer_tags=("reasoning",),
    )
    memory = ConversationMemory(path=tmp_path / "memory.json")
    return ZenithAssistant(config=config, memory=memory, council_mode=council_mode)


@pytest.mark.asyncio
async def test_local_tool_answers_without_model(tmp_path):
    zen = make_assistant(tmp_path)
    result = await zen.ask("hesapla: 3*3")
    assert result.text == "Sonuc: 9"
    assert result.source == "local"
    assert zen.memory.messages[-1]["content"] == "Sonuc: 9"


@pytest.mark.asyncio
async def test_model_answer_records_contributor(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        return ModelReply("m1", "p/m1", "model cevabi")

    monkeypatch.setattr(assistant_module.router, "ask", fake_router_ask)

    result = await zen.ask("nasilsin?")
    assert result.text == "model cevabi"
    assert result.source == "model"
    assert result.contributors == ["m1"]


@pytest.mark.asyncio
async def test_search_command_feeds_results_to_model(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)
    captured = {}

    async def fake_search(query, max_results=5):
        captured["query"] = query
        return [SearchResult(title="Baslik", url="https://x", snippet="ozet")]

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        captured["prompt"] = messages[-1]["content"]
        return ModelReply("m1", "p/m1", "arama destekli cevap")

    monkeypatch.setattr(assistant_module.websearch, "search", fake_search)
    monkeypatch.setattr(assistant_module.router, "ask", fake_router_ask)

    result = await zen.ask("ara: bugun dolar kuru")
    assert result.text == "arama destekli cevap"
    assert result.source == "search"
    assert captured["query"] == "bugun dolar kuru"
    assert "Baslik" in captured["prompt"]
    # Hafizaya ham arama sonuclari degil, soru + nihai cevap yazilir.
    assert zen.memory.messages[-2]["content"] == "ara: bugun dolar kuru"
    assert zen.memory.messages[-1]["content"] == "arama destekli cevap"


@pytest.mark.asyncio
async def test_skill_command_answers_directly(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)

    async def fake_weather(city):
        return f"{city} icin hava: gunesli"

    monkeypatch.setattr(assistant_module.skills, "weather", fake_weather)

    result = await zen.ask("hava: Bursa")
    assert result.source == "skill"
    assert "gunesli" in result.text
    # Skill cevabi hafizaya yazilir.
    assert zen.memory.messages[-1]["content"] == result.text


@pytest.mark.asyncio
async def test_summarize_command_feeds_page_to_model(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)
    captured = {}

    async def fake_fetch(url, max_chars=6000):
        captured["url"] = url
        return "sayfa metni burada"

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        captured["prompt"] = messages[-1]["content"]
        return ModelReply("m1", "p/m1", "ozet cevabi")

    monkeypatch.setattr(assistant_module.skills, "fetch_page_text", fake_fetch)
    monkeypatch.setattr(assistant_module.router, "ask", fake_router_ask)

    result = await zen.ask("ozetle: https://ornek.com")
    assert result.source == "summary"
    assert result.text == "ozet cevabi"
    assert captured["url"] == "https://ornek.com"
    assert "sayfa metni burada" in captured["prompt"]


@pytest.mark.asyncio
async def test_model_and_system_overrides_are_passed_through(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)
    captured = {}

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        captured["preferred"] = preferred
        captured["system"] = messages[0]["content"]
        return ModelReply("m1", "p/m1", "cevap")

    monkeypatch.setattr(assistant_module.router, "ask", fake_router_ask)

    await zen.ask("selam", model="m1", system="ozel kisilik")
    assert captured["preferred"] == "m1"
    assert captured["system"] == "ozel kisilik"


@pytest.mark.asyncio
async def test_search_failure_is_graceful(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)

    async def fake_search(query, max_results=5):
        raise SearchError("ag yok")

    monkeypatch.setattr(assistant_module.websearch, "search", fake_search)

    result = await zen.ask("ara: hava durumu")
    assert result.source == "search"
    assert result.text.startswith("[arama hatasi]")
