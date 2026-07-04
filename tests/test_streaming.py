import pytest

from zenith import assistant as assistant_module
from zenith import router
from zenith.assistant import ZenithAssistant
from zenith.config import ModelSpec, ZenithConfig
from zenith.memory import ConversationMemory
from zenith.providers import ProviderError


def make_config(*specs: ModelSpec) -> ZenithConfig:
    return ZenithConfig(models=specs, council_max_parallel=4, synthesizer_tags=("reasoning",))


def make_assistant(tmp_path) -> ZenithAssistant:
    config = make_config(ModelSpec("m1", "p/m1", "p", None, (), priority=1))
    return ZenithAssistant(config=config, memory=ConversationMemory(path=tmp_path / "m.json"))


async def _fake_stream(pieces):
    for p in pieces:
        yield p


@pytest.mark.asyncio
async def test_router_stream_yields_model_then_deltas(monkeypatch):
    spec = ModelSpec("m1", "p/m1", "p", None, (), priority=1)
    config = make_config(spec)

    def fake_stream_model(spec, messages, **kwargs):
        return _fake_stream(["Mer", "haba", " dunya"])

    monkeypatch.setattr(router, "stream_model", fake_stream_model)

    events = [ev async for ev in router.ask_stream(config, [{"role": "user", "content": "hi"}])]
    assert events[0] == ("model", "m1")
    assert [v for k, v in events if k == "delta"] == ["Mer", "haba", " dunya"]


@pytest.mark.asyncio
async def test_router_stream_falls_back_when_first_model_fails(monkeypatch):
    spec_a = ModelSpec("a", "p/a", "p", None, (), priority=1)
    spec_b = ModelSpec("b", "p/b", "p", None, (), priority=2)
    config = make_config(spec_a, spec_b)

    async def failing():
        raise ProviderError("a", Exception("down"))
        yield  # pragma: no cover - generator olmasi icin

    def fake_stream_model(spec, messages, **kwargs):
        if spec.name == "a":
            return failing()
        return _fake_stream(["ok"])

    monkeypatch.setattr(router, "stream_model", fake_stream_model)

    events = [ev async for ev in router.ask_stream(config, [{"role": "user", "content": "hi"}])]
    assert ("model", "b") in events
    assert ("delta", "ok") in events


@pytest.mark.asyncio
async def test_assistant_stream_plain_model(monkeypatch, tmp_path):
    zen = make_assistant(tmp_path)

    def fake_ask_stream(config, messages, tags=(), preferred=None):
        return _stream_pairs([("model", "m1"), ("delta", "Sel"), ("delta", "am")])

    async def _stream_pairs(pairs):
        for p in pairs:
            yield p

    monkeypatch.setattr(assistant_module.router, "ask_stream", fake_ask_stream)

    events = [ev async for ev in zen.ask_stream("selam")]
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == "Selam"
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["source"] == "model"
    assert meta["contributors"] == ["m1"]
    assert events[-1]["type"] == "done"
    # Tam metin hafizaya yazilmis olmali.
    assert zen.memory.messages[-1]["content"] == "Selam"


@pytest.mark.asyncio
async def test_assistant_stream_local_tool_is_single_shot(tmp_path):
    zen = make_assistant(tmp_path)
    events = [ev async for ev in zen.ask_stream("hesapla: 6*7")]
    assert events[0] == {"type": "delta", "text": "Sonuc: 42"}
    assert any(e["type"] == "meta" and e["source"] == "local" for e in events)
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_endpoint_emits_sse(monkeypatch):
    from fastapi.testclient import TestClient

    from zenith import server
    from zenith.assistant import AskResult

    async def fake_ask_stream(self, message, **kwargs):
        yield {"type": "delta", "text": "merhaba"}
        yield {"type": "meta", "source": "model", "contributors": ["m1"]}
        yield {"type": "done"}

    monkeypatch.setattr(server.ZenithAssistant, "ask_stream", fake_ask_stream)
    client = TestClient(server.app)
    with client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "data:" in body
    assert "merhaba" in body
    assert '"type": "done"' in body
