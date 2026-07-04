import pytest

from zenith import agent as agent_module
from zenith import assistant as assistant_module
from zenith.assistant import ZenithAssistant
from zenith.config import ModelSpec, ZenithConfig
from zenith.memory import ConversationMemory
from zenith.notes import NotesStore
from zenith.profile import ProfileStore
from zenith.providers import ModelReply
from zenith.rag import DocStore, chunk_text


def make_assistant(tmp_path, **kw) -> ZenithAssistant:
    config = ZenithConfig(
        models=(ModelSpec("m1", "p/m1", "p", None, ("reasoning",), priority=1),),
        council_max_parallel=4,
        synthesizer_tags=("reasoning",),
    )
    return ZenithAssistant(
        config=config,
        memory=ConversationMemory(path=tmp_path / "m.json"),
        notes=NotesStore(path=tmp_path / "n.json"),
        profile=ProfileStore(path=tmp_path / "p.json"),
        docs=DocStore(path=tmp_path / "d.json"),
        **kw,
    )


# --- Profil (uzun sureli hafiza) ---
def test_profile_store_persists(tmp_path):
    store = ProfileStore(path=tmp_path / "p.json")
    store.add("Adim Can")
    store.add("Python seviyorum")
    store.add("Adim Can")  # tekrar eklenmez
    assert store.list() == ["Adim Can", "Python seviyorum"]
    assert "Adim Can" in store.as_prompt()
    assert ProfileStore(path=tmp_path / "p.json").list() == ["Adim Can", "Python seviyorum"]


@pytest.mark.asyncio
async def test_profile_injected_into_system_prompt(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)
    await zen.ask("beni hatirla: adim Can")

    captured = {}

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        captured["system"] = messages[0]["content"]
        return ModelReply("m1", "p/m1", "selam Can")

    monkeypatch.setattr(assistant_module.router, "ask", fake_router_ask)
    await zen.ask("merhaba", history=[])
    assert "adim Can" in captured["system"]


# --- RAG ---
def test_chunk_text_overlaps():
    text = "a" * 2000
    chunks = chunk_text(text, size=800, overlap=150)
    assert len(chunks) >= 3
    assert all(len(c) <= 800 for c in chunks)


def test_docstore_retrieve_ranks_relevant(tmp_path):
    store = DocStore(path=tmp_path / "d.json")
    store.add_document("kedi.txt", "Kediler bagimsiz hayvanlardir ve balik sever.")
    store.add_document("araba.txt", "Arabalar tekerlekli tasitlardir, benzinle calisir.")
    hits = store.retrieve("kedi ne yer")
    assert hits
    assert hits[0].doc == "kedi.txt"


@pytest.mark.asyncio
async def test_rag_injects_document_context(tmp_path, monkeypatch):
    zen = make_assistant(tmp_path)
    zen.docs.add_document("gizli.txt", "Zenith parolasi mavi-kaplan-42'dir.")

    captured = {}

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        captured["prompt"] = messages[-1]["content"]
        return ModelReply("m1", "p/m1", "Parola mavi-kaplan-42.")

    monkeypatch.setattr(assistant_module.router, "ask", fake_router_ask)
    result = await zen.ask("zenith parolasi nedir", history=[])
    assert result.source == "rag"
    assert "mavi-kaplan-42" in captured["prompt"]


# --- Ajan (fonksiyon cagirma) ---
@pytest.mark.asyncio
async def test_agent_calls_tool_then_answers(tmp_path, monkeypatch):
    config = ZenithConfig(
        models=(ModelSpec("m1", "p/m1", "p", None, ("reasoning",), priority=1),),
        council_max_parallel=4,
        synthesizer_tags=("reasoning",),
    )
    steps = [
        "ARAC: hava | Istanbul",
        "CEVAP: Istanbul'da hava gunesli.",
    ]

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        return ModelReply("m1", "p/m1", steps.pop(0))

    async def fake_weather(city):
        return f"{city}: gunesli, 25C"

    monkeypatch.setattr(agent_module, "router_ask", fake_router_ask)
    monkeypatch.setattr(agent_module.skills, "weather", fake_weather)
    # TOOLS 'hava' girisini de guncelle (import aninda baglanmisti).
    agent_module.TOOLS["hava"] = (fake_weather, agent_module.TOOLS["hava"][1])

    answer, used = await agent_module.run(config, "Istanbul'da hava nasil?")
    assert "gunesli" in answer
    assert "hava" in used


@pytest.mark.asyncio
async def test_agent_direct_answer_without_tool(tmp_path, monkeypatch):
    config = ZenithConfig(
        models=(ModelSpec("m1", "p/m1", "p", None, ("reasoning",), priority=1),),
        council_max_parallel=4,
        synthesizer_tags=("reasoning",),
    )

    async def fake_router_ask(config, messages, tags=(), preferred=None):
        return ModelReply("m1", "p/m1", "CEVAP: 2 + 2 = 4.")

    monkeypatch.setattr(agent_module, "router_ask", fake_router_ask)
    answer, used = await agent_module.run(config, "2+2 kac?")
    assert "4" in answer
    assert used == []
