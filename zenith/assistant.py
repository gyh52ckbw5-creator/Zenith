"""ZenithAssistant: hafiza, yerel araclar, web aramasi, tek-model router'i ve
konsey modunu bir araya getiren ana kisilik/orkestrasyon katmani."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import council, router, tools, websearch
from .config import ZenithConfig, load_config
from .memory import ConversationMemory

SYSTEM_PROMPT = (
    "Sen Zenith adinda, kullanicinin kisisel yapay zeka asistanisin. Birden "
    "fazla ucretsiz yapay zeka modelinin gucunu birlestirerek calisiyorsun. "
    "Kisa, net, samimi ve yardimsever cevaplar ver. Emin olmadigin konularda "
    "bunu belirt."
)

SEARCH_PATTERN = re.compile(r"^\s*(?:ara|search)\s*[:=]\s*(.+)$", re.IGNORECASE)

SEARCH_ANSWER_PROMPT = (
    "Asagida kullanicinin sorgusu icin guncel web arama sonuclari var. Bu "
    "sonuclara dayanarak soruyu cevapla; hangi kaynaktan yararlandiginsa "
    "[1], [2] gibi numaralarla belirt. Sonuclar yetersizse bunu soyle."
)


@dataclass
class AskResult:
    """Bir sorunun cevabi + nasil uretildigine dair meta bilgi."""

    text: str
    source: str = "model"  # "local" | "model" | "council" | "search"
    contributors: list[str] = field(default_factory=list)


class ZenithAssistant:
    def __init__(
        self,
        config: ZenithConfig | None = None,
        memory: ConversationMemory | None = None,
        council_mode: bool = False,
    ):
        self.config = config or load_config()
        self.memory = memory if memory is not None else ConversationMemory()
        self.council_mode = council_mode

    async def ask(self, user_input: str, *, tags: tuple[str, ...] = ()) -> AskResult:
        local_reply = tools.try_handle_locally(user_input)
        if local_reply is not None:
            self._remember(user_input, local_reply)
            return AskResult(text=local_reply, source="local")

        search_match = SEARCH_PATTERN.match(user_input)
        if search_match:
            return await self._ask_with_search(user_input, search_match.group(1), tags)

        self.memory.add("user", user_input)
        messages = self.memory.as_messages(SYSTEM_PROMPT)
        result = await self._ask_models(messages, tags)
        self.memory.add("assistant", result.text)
        return result

    async def _ask_models(self, messages: list[dict], tags: tuple[str, ...]) -> AskResult:
        if self.council_mode:
            outcome = await council.ask(self.config, messages, tags=tags)
            return AskResult(
                text=outcome.final_answer,
                source="council",
                contributors=[op.model_name for op in outcome.contributors],
            )
        reply = await router.ask(self.config, messages, tags=tags)
        return AskResult(text=reply.content, source="model", contributors=[reply.model_name])

    async def _ask_with_search(
        self, user_input: str, query: str, tags: tuple[str, ...]
    ) -> AskResult:
        try:
            results = await websearch.search(query)
        except websearch.SearchError as exc:
            text = f"[arama hatasi] {exc}"
            self._remember(user_input, text)
            return AskResult(text=text, source="search")

        findings = websearch.format_results(results)
        self.memory.add("user", user_input)
        messages = self.memory.as_messages(SYSTEM_PROMPT)
        # Arama sonuclarini yalnizca bu soruya eklenen gecici baglam olarak ver;
        # hafizaya ham sonuclar degil, kullanici sorusu + nihai cevap yazilir.
        messages[-1] = {
            "role": "user",
            "content": f"{SEARCH_ANSWER_PROMPT}\n\nSorgu: {query}\n\nArama sonuclari:\n{findings}",
        }
        result = await self._ask_models(messages, tags)
        result.source = "search"
        self.memory.add("assistant", result.text)
        return result

    def _remember(self, user_input: str, reply: str) -> None:
        self.memory.add("user", user_input)
        self.memory.add("assistant", reply)

    def list_models(self) -> list[str]:
        lines = []
        for spec in self.config.models:
            status = "hazir" if spec.is_available() else "anahtar/lokal eksik"
            lines.append(f"- {spec.name} ({spec.provider}, oncelik={spec.priority}): {status}")
        return lines
