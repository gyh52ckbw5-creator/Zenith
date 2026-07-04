import pytest

from zenith.assistant import ZenithAssistant
from zenith.config import ModelSpec, ZenithConfig
from zenith.memory import ConversationMemory
from zenith.notes import NotesStore


def make_assistant(tmp_path) -> ZenithAssistant:
    config = ZenithConfig(
        models=(ModelSpec("m1", "p/m1", "p", None, (), priority=1),),
        council_max_parallel=4,
        synthesizer_tags=("reasoning",),
    )
    return ZenithAssistant(
        config=config,
        memory=ConversationMemory(path=tmp_path / "m.json"),
        notes=NotesStore(path=tmp_path / "notes.json"),
    )


def test_notes_store_add_list_delete(tmp_path):
    store = NotesStore(path=tmp_path / "n.json")
    assert store.add("sut al") == 1
    assert store.add("faturayi ode") == 2
    assert len(store.list()) == 2
    assert store.delete(1) is True
    assert store.list()[0]["text"] == "faturayi ode"
    assert store.delete(99) is False


def test_notes_persist_across_instances(tmp_path):
    path = tmp_path / "n.json"
    NotesStore(path=path).add("hatirla beni")
    assert NotesStore(path=path).list()[0]["text"] == "hatirla beni"


@pytest.mark.asyncio
async def test_assistant_note_add_and_list(tmp_path):
    zen = make_assistant(tmp_path)
    add = await zen.ask("not: yarin doktora git")
    assert add.source == "skill"
    assert "eklendi" in add.text

    listed = await zen.ask("notlarim")
    assert "yarin doktora git" in listed.text


@pytest.mark.asyncio
async def test_assistant_note_delete_and_clear(tmp_path):
    zen = make_assistant(tmp_path)
    await zen.ask("not: bir")
    await zen.ask("not: iki")
    deleted = await zen.ask("not sil 1")
    assert "silindi" in deleted.text
    assert "iki" in (await zen.ask("notlarim")).text

    cleared = await zen.ask("notlari temizle")
    assert "temizlendi" in cleared.text
    assert "yok" in (await zen.ask("notlarim")).text
