"""Hafıza sistemi testleri."""

from __future__ import annotations

import pytest
from pathlib import Path
from zenith.memory_system import MemorySystem


@pytest.fixture
def memory(tmp_path: Path) -> MemorySystem:
    """Geçici hafıza oluştur."""
    return MemorySystem(path=tmp_path / "memory.json")


def test_add_memory(memory: MemorySystem):
    """Hafıza ekle."""
    mem_id = memory.add_memory(
        "Ali'nin favori yemeği mantı.",
        category="preference",
        importance=0.8
    )
    assert mem_id in memory.memories
    assert memory.memories[mem_id].content == "Ali'nin favori yemeği mantı."


def test_recall_memory(memory: MemorySystem):
    """Hafızayı geri çağır."""
    memory.add_memory("Python'da async async/await ile yapılır.", tags=["python"])
    memory.add_memory("Türkiye'nin başkenti Ankara'dır.", tags=["geografi"])
    
    results = memory.recall_memory("python")
    assert len(results) > 0
    assert "Python" in results[0].content


def test_forget_memory(memory: MemorySystem):
    """Hafızayı unut."""
    mem_id = memory.add_memory("Bir test hafızası.")
    assert mem_id in memory.memories
    
    result = memory.forget_memory(mem_id)
    assert result is True
    assert mem_id not in memory.memories


def test_memory_summary(memory: MemorySystem):
    """Hafıza özeti."""
    memory.add_memory("Fact 1", category="fact")
    memory.add_memory("Fact 2", category="fact")
    memory.add_memory("Event 1", category="event")
    
    summary = memory.get_memory_summary()
    assert summary["total_memories"] == 3
    assert summary["by_category"]["fact"] == 2
    assert summary["by_category"]["event"] == 1
