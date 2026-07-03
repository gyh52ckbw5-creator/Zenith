"""ZenithAssistant: hafiza, yerel araclar, tek-model router'i ve konsey
modunu bir araya getiren ana kisilik/orkestrasyon katmani."""

from __future__ import annotations

from . import council, router, tools
from .config import ZenithConfig, load_config
from .memory import ConversationMemory

SYSTEM_PROMPT = (
    "Sen Zenith adinda, kullanicinin kisisel yapay zeka asistanisin. Birden "
    "fazla ucretsiz yapay zeka modelinin gucunu birlestirerek calisiyorsun. "
    "Kisa, net, samimi ve yardimsever cevaplar ver. Emin olmadigin konularda "
    "bunu belirt."
)


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

    async def ask(self, user_input: str, *, tags: tuple[str, ...] = ()) -> str:
        local_reply = tools.try_handle_locally(user_input)
        if local_reply is not None:
            self.memory.add("user", user_input)
            self.memory.add("assistant", local_reply)
            return local_reply

        self.memory.add("user", user_input)
        messages = self.memory.as_messages(SYSTEM_PROMPT)

        if self.council_mode:
            result = await council.ask(self.config, messages, tags=tags)
            answer = result.final_answer
        else:
            reply = await router.ask(self.config, messages, tags=tags)
            answer = reply.content

        self.memory.add("assistant", answer)
        return answer

    def list_models(self) -> list[str]:
        lines = []
        for spec in self.config.models:
            status = "hazir" if spec.is_available() else "anahtar/lokal eksik"
            lines.append(f"- {spec.name} ({spec.provider}, oncelik={spec.priority}): {status}")
        return lines
