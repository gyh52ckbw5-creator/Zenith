from pathlib import Path

from zenith.memory import ConversationMemory, default_memory_path


def test_memory_persists_and_reloads(tmp_path):
    path = tmp_path / "memory.json"
    mem = ConversationMemory(path=path)
    mem.add("user", "merhaba")
    mem.add("assistant", "selam!")

    reloaded = ConversationMemory(path=path)
    assert reloaded.messages == [
        {"role": "user", "content": "merhaba"},
        {"role": "assistant", "content": "selam!"},
    ]


def test_memory_trims_old_turns(tmp_path):
    mem = ConversationMemory(path=tmp_path / "memory.json", max_turns=3)
    for i in range(5):
        mem.add("user", f"msg-{i}")

    assert len(mem.messages) == 3
    assert mem.messages[0]["content"] == "msg-2"


def test_memory_reset(tmp_path):
    mem = ConversationMemory(path=tmp_path / "memory.json")
    mem.add("user", "hi")
    mem.reset()
    assert mem.messages == []


def test_default_memory_path_respects_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom.json"
    monkeypatch.setenv("ZENITH_MEMORY_PATH", str(custom))
    assert default_memory_path() == custom


def test_default_memory_path_uses_tmp_on_vercel(monkeypatch):
    monkeypatch.delenv("ZENITH_MEMORY_PATH", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert default_memory_path() == Path("/tmp/zenith-memory.json")


def test_as_messages_prepends_system_prompt(tmp_path):
    mem = ConversationMemory(path=tmp_path / "memory.json")
    mem.add("user", "hi")
    messages = mem.as_messages("system prompt")
    assert messages[0] == {"role": "system", "content": "system prompt"}
    assert messages[1] == {"role": "user", "content": "hi"}
