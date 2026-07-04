"""Gelişmiş hafıza sistemi - kişisel uzun vadeli hafıza.

Uzun vadeli hafıza, unutma eğrileri, hafıza geri çağırma, vb.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import json
from pathlib import Path
import os


@dataclass
class Memory:
    """Bir hafıza kaydı."""
    id: str
    content: str
    category: str  # "personal", "fact", "event", "preference"
    importance: float  # 0.0 - 1.0
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    related_memories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class MemorySystem:
    """Gelişmiş hafıza yönetimi sistemi."""

    def __init__(self, path: Path | None = None):
        env_path = os.environ.get("ZENITH_MEMORY_PATH")
        if env_path:
            self.path = Path(env_path)
        elif os.environ.get("VERCEL"):
            self.path = Path("/tmp/zenith-advanced-memory.json")
        else:
            self.path = Path.home() / ".zenith" / "advanced-memory.json"
        
        self.memories: dict[str, Memory] = self._load()
        self.max_memories = 10000
        self.forget_threshold = 0.2  # Önemsizlik eşiği

    def _load(self) -> dict[str, Memory]:
        """Hafızaları yükle."""
        if not self.path.exists():
            return {}
        try:
            with open(self.path) as f:
                data = json.load(f)
            memories = {}
            for mem_id, mem_data in data.items():
                memories[mem_id] = Memory(
                    id=mem_data["id"],
                    content=mem_data["content"],
                    category=mem_data["category"],
                    importance=mem_data["importance"],
                    created_at=datetime.fromisoformat(mem_data["created_at"]),
                    last_accessed=datetime.fromisoformat(mem_data["last_accessed"]),
                    access_count=mem_data["access_count"],
                    related_memories=mem_data.get("related_memories", []),
                    tags=mem_data.get("tags", []),
                )
            return memories
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        """Hafızaları kaydet."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for mem_id, mem in self.memories.items():
            data[mem_id] = {
                "id": mem.id,
                "content": mem.content,
                "category": mem.category,
                "importance": mem.importance,
                "created_at": mem.created_at.isoformat(),
                "last_accessed": mem.last_accessed.isoformat(),
                "access_count": mem.access_count,
                "related_memories": mem.related_memories,
                "tags": mem.tags,
            }
        with open(self.path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_memory(self, content: str, category: str = "fact", importance: float = 0.5, tags: list[str] | None = None) -> str:
        """Yeni hafıza ekle."""
        import uuid
        mem_id = str(uuid.uuid4())
        now = datetime.now()
        memory = Memory(
            id=mem_id,
            content=content,
            category=category,
            importance=importance,
            created_at=now,
            last_accessed=now,
            tags=tags or [],
        )
        self.memories[mem_id] = memory
        self._cleanup_old_memories()
        self._save()
        return mem_id

    def recall_memory(self, query: str) -> list[Memory]:
        """Hafızaları sorguya göre geri çağır."""
        query_lower = query.lower()
        matches = []
        for memory in self.memories.values():
            if query_lower in memory.content.lower() or any(tag in query_lower for tag in memory.tags):
                memory.last_accessed = datetime.now()
                memory.access_count += 1
                matches.append(memory)
        
        # Önemsiz olanları çıkar
        matches = [m for m in matches if m.importance > self.forget_threshold]
        # Önemliye göre sırala
        matches.sort(key=lambda m: (-m.importance, -m.access_count))
        self._save()
        return matches[:5]  # Top 5

    def forget_memory(self, mem_id: str) -> bool:
        """Hafızayı unut."""
        if mem_id in self.memories:
            del self.memories[mem_id]
            self._save()
            return True
        return False

    def _cleanup_old_memories(self) -> None:
        """Eski ve önemsiz hafızaları temizle."""
        if len(self.memories) > self.max_memories:
            # En az önemlileri sil
            sorted_mems = sorted(
                self.memories.items(),
                key=lambda x: (-x[1].importance, -x[1].access_count, x[1].created_at)
            )
            to_delete = len(self.memories) - self.max_memories
            for mem_id, _ in sorted_mems[-to_delete:]:
                del self.memories[mem_id]

    def get_memory_summary(self) -> dict[str, Any]:
        """Hafıza özeti."""
        categories = {}
        for mem in self.memories.values():
            if mem.category not in categories:
                categories[mem.category] = 0
            categories[mem.category] += 1
        
        return {
            "total_memories": len(self.memories),
            "by_category": categories,
            "average_importance": sum(m.importance for m in self.memories.values()) / len(self.memories) if self.memories else 0,
        }
