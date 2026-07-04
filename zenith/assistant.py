"""ZenithAssistant: hafiza, yerel araclar, web aramasi, tek-model router'i ve
konsey modunu bir araya getiren ana kisilik/orkestrasyon katmani."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import council, router, skills, tools, websearch
from .config import ZenithConfig, load_config
from .memory import ConversationMemory
from .notes import NotesStore

DEFAULT_SYSTEM_PROMPT = (
    "Sen Zenith'sin: Iron Man'deki Jarvis tarzinda, kullanicinin kisisel "
    "yapay zeka asistani. Birden fazla acik kaynak ve ucretsiz yapay zeka "
    "modelinin gucunu birlestirerek calisiyorsun. Uslubun: zeki, sakin, "
    "hafif esprili ve her zaman cozum odakli. Kullanicina ara sira 'efendim' "
    "diye hitap edebilirsin ama abartma. Cevaplarin kisa ve net olsun; "
    "gerektiginde adim adim acikla. Emin olmadigin konularda bunu durustce "
    "soyle, uydurma. Kullanici Turkce yazarsa Turkce, baska dilde yazarsa o "
    "dilde cevap ver."
)


def system_prompt() -> str:
    """Kisilik ZENITH_SYSTEM_PROMPT ortam degiskeniyle ozellestirilebilir."""
    return os.environ.get("ZENITH_SYSTEM_PROMPT") or DEFAULT_SYSTEM_PROMPT


# Geriye donuk uyumluluk icin eski ad korunur.
SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT

SEARCH_PATTERN = re.compile(r"^\s*(?:ara|search)\s*[:=]\s*(.+)$", re.IGNORECASE)

SEARCH_ANSWER_PROMPT = (
    "Asagida kullanicinin sorgusu icin guncel web arama sonuclari var. Bu "
    "sonuclara dayanarak soruyu cevapla; hangi kaynaktan yararlandiginsa "
    "[1], [2] gibi numaralarla belirt. Sonuclar yetersizse bunu soyle."
)

SUMMARIZE_PROMPT = (
    "Asagida bir web sayfasindan cikarilan metin var. Bu icerigi Turkce, "
    "kisa ve anlasilir sekilde ozetle; onemli noktalari maddeler halinde ver."
)

# Dogrudan bir cevap ureten (modele gitmeyen) yetenek komutlari.
# Her desen tek bir argumani yakalar; eslesirse skills modulundeki ilgili
# fonksiyon CAGRI ANINDA (isimle) cozulur - boylece test/monkeypatch calisir.
_DIRECT_SKILLS = [
    (re.compile(r"^\s*(?:wiki|vikipedi)\s*[:=]\s*(.+)$", re.IGNORECASE), "wikipedia"),
    (re.compile(r"^\s*(?:hava|weather)\s*[:=]\s*(.+)$", re.IGNORECASE), "weather"),
    (re.compile(r"^\s*(?:kur|doviz|currency)\s*[:=]\s*(.+)$", re.IGNORECASE), "currency"),
    (re.compile(r"^\s*(?:haberler|haber|news)\b\s*[:=]?\s*(.*)$", re.IGNORECASE), "news"),
    (re.compile(r"^\s*(?:sozluk|sözlük|dictionary|tanim)\s*[:=]\s*(.+)$", re.IGNORECASE), "dictionary"),
    (re.compile(r"^\s*(?:sifre|şifre|password)\b\s*(?:uret|üret)?\s*[:=]?\s*(.*)$", re.IGNORECASE), "password"),
    (
        re.compile(r"^\s*(?:kullanici|kullanıcı|sherlock|username)\s*[:=]\s*(.+)$", re.IGNORECASE),
        "username_search",
    ),
]

SUMMARIZE_PATTERN = re.compile(r"^\s*(?:ozetle|özetle|summarize)\s*[:=]\s*(\S+)\s*$", re.IGNORECASE)

# --- Notlar (durumsal): ekle / listele / sil / temizle ---
NOTE_ADD_PATTERN = re.compile(r"^\s*(?:not|hatirlat|hatırlat|note)\s*[:=]\s*(.+)$", re.IGNORECASE)
NOTE_LIST_PATTERN = re.compile(r"^\s*(?:notlar|notlarim|notlarım|notes)\s*$", re.IGNORECASE)
NOTE_DELETE_PATTERN = re.compile(r"^\s*not(?:u)?\s+sil\s+(\d+)\s*$", re.IGNORECASE)
NOTE_CLEAR_PATTERN = re.compile(r"^\s*notlar(?:i|ı)?\s+temizle\s*$", re.IGNORECASE)


@dataclass
class AskResult:
    """Bir sorunun cevabi + nasil uretildigine dair meta bilgi."""

    text: str
    # "local" | "model" | "council" | "search" | "skill" | "summary"
    source: str = "model"
    contributors: list[str] = field(default_factory=list)


class ZenithAssistant:
    def __init__(
        self,
        config: ZenithConfig | None = None,
        memory: ConversationMemory | None = None,
        council_mode: bool = False,
        notes: NotesStore | None = None,
    ):
        self.config = config or load_config()
        self.memory = memory if memory is not None else ConversationMemory()
        self.council_mode = council_mode
        self.notes = notes if notes is not None else NotesStore()

    def _handle_notes(self, user_input: str) -> str | None:
        """Not komutlarini isler; eslesmezse None doner."""
        add = NOTE_ADD_PATTERN.match(user_input)
        if add:
            count = self.notes.add(add.group(1).strip())
            return f"Not eklendi (#{count}). 'notlarim' ile hepsini gorebilirsin."

        if NOTE_LIST_PATTERN.match(user_input):
            items = self.notes.list()
            if not items:
                return "Henuz notun yok. 'not: ...' ile ekleyebilirsin."
            lines = [f"{i + 1}. {it['text']}  _({it['at']})_" for i, it in enumerate(items)]
            return "**Notlarin:**\n" + "\n".join(lines)

        delete = NOTE_DELETE_PATTERN.match(user_input)
        if delete:
            ok = self.notes.delete(int(delete.group(1)))
            return "Not silindi." if ok else "O numarada bir not yok."

        if NOTE_CLEAR_PATTERN.match(user_input):
            self.notes.clear()
            return "Tum notlar temizlendi."

        return None

    async def ask(
        self,
        user_input: str,
        *,
        tags: tuple[str, ...] = (),
        model: str | None = None,
        system: str | None = None,
    ) -> AskResult:
        result = await self._resolve_non_streaming(user_input, tags, model, system)
        if result is not None:
            return result

        # Duz model yolu (konsey degil): tek seferde topla.
        self.memory.add("user", user_input)
        messages = self.memory.as_messages(system or system_prompt())
        reply = await router.ask(self.config, messages, tags=tags, preferred=model)
        self.memory.add("assistant", reply.content)
        return AskResult(text=reply.content, source="model", contributors=[reply.model_name])

    async def ask_stream(
        self,
        user_input: str,
        *,
        tags: tuple[str, ...] = (),
        model: str | None = None,
        system: str | None = None,
    ):
        """`ask` ile ayni yollari izler; duz model yolunda cevabi token token
        akitir. Her adimda bir olay sozlugu uretir:
          {"type":"delta","text":...} | {"type":"meta",...} | {"type":"done"}
        """
        result = await self._resolve_non_streaming(user_input, tags, model, system)
        if result is not None:
            yield {"type": "delta", "text": result.text}
            yield {"type": "meta", "source": result.source, "contributors": result.contributors}
            yield {"type": "done"}
            return

        self.memory.add("user", user_input)
        messages = self.memory.as_messages(system or system_prompt())
        chunks: list[str] = []
        model_name: str | None = None
        async for kind, value in router.ask_stream(
            self.config, messages, tags=tags, preferred=model
        ):
            if kind == "model":
                model_name = value
            else:
                chunks.append(value)
                yield {"type": "delta", "text": value}

        text = "".join(chunks).strip()
        self.memory.add("assistant", text)
        yield {
            "type": "meta",
            "source": "model",
            "contributors": [model_name] if model_name else [],
        }
        yield {"type": "done"}

    async def _resolve_non_streaming(
        self, user_input: str, tags: tuple[str, ...], model: str | None, system: str | None
    ) -> AskResult | None:
        """Akitilamayan (tam sonuc donen) yollari isler: yerel arac, yetenek,
        ozetleme, arama, konsey. Duz model yolu icin None doner (akitilacak)."""
        local_reply = tools.try_handle_locally(user_input)
        if local_reply is not None:
            self._remember(user_input, local_reply)
            return AskResult(text=local_reply, source="local")

        note_reply = self._handle_notes(user_input)
        if note_reply is not None:
            self._remember(user_input, note_reply)
            return AskResult(text=note_reply, source="skill")

        for pattern, handler_name in _DIRECT_SKILLS:
            match = pattern.match(user_input)
            if match:
                handler = getattr(skills, handler_name)
                reply = await handler(match.group(1).strip())
                self._remember(user_input, reply)
                return AskResult(text=reply, source="skill")

        summarize_match = SUMMARIZE_PATTERN.match(user_input)
        if summarize_match:
            return await self._ask_with_summary(
                user_input, summarize_match.group(1), tags, model, system
            )

        search_match = SEARCH_PATTERN.match(user_input)
        if search_match:
            return await self._ask_with_search(
                user_input, search_match.group(1), tags, model, system
            )

        if self.council_mode:
            self.memory.add("user", user_input)
            messages = self.memory.as_messages(system or system_prompt())
            result = await self._ask_models(messages, tags, model)
            self.memory.add("assistant", result.text)
            return result

        return None

    async def _ask_models(
        self, messages: list[dict], tags: tuple[str, ...], model: str | None = None
    ) -> AskResult:
        if self.council_mode:
            outcome = await council.ask(self.config, messages, tags=tags)
            return AskResult(
                text=outcome.final_answer,
                source="council",
                contributors=[op.model_name for op in outcome.contributors],
            )
        reply = await router.ask(self.config, messages, tags=tags, preferred=model)
        return AskResult(text=reply.content, source="model", contributors=[reply.model_name])

    async def _ask_with_search(
        self,
        user_input: str,
        query: str,
        tags: tuple[str, ...],
        model: str | None = None,
        system: str | None = None,
    ) -> AskResult:
        try:
            results = await websearch.search(query)
        except websearch.SearchError as exc:
            text = f"[arama hatasi] {exc}"
            self._remember(user_input, text)
            return AskResult(text=text, source="search")

        findings = websearch.format_results(results)
        self.memory.add("user", user_input)
        messages = self.memory.as_messages(system or system_prompt())
        # Arama sonuclarini yalnizca bu soruya eklenen gecici baglam olarak ver;
        # hafizaya ham sonuclar degil, kullanici sorusu + nihai cevap yazilir.
        messages[-1] = {
            "role": "user",
            "content": f"{SEARCH_ANSWER_PROMPT}\n\nSorgu: {query}\n\nArama sonuclari:\n{findings}",
        }
        result = await self._ask_models(messages, tags, model)
        result.source = "search"
        self.memory.add("assistant", result.text)
        return result

    async def _ask_with_summary(
        self,
        user_input: str,
        url: str,
        tags: tuple[str, ...],
        model: str | None = None,
        system: str | None = None,
    ) -> AskResult:
        try:
            page_text = await skills.fetch_page_text(url)
        except skills.SkillError as exc:
            text = f"[ozetleme hatasi] {exc}"
            self._remember(user_input, text)
            return AskResult(text=text, source="summary")

        if not page_text.strip():
            text = "Sayfadan metin cikarilamadi (bos ya da JS ile yuklenen icerik)."
            self._remember(user_input, text)
            return AskResult(text=text, source="summary")

        self.memory.add("user", user_input)
        messages = self.memory.as_messages(system or system_prompt())
        messages[-1] = {
            "role": "user",
            "content": f"{SUMMARIZE_PROMPT}\n\nKaynak: {url}\n\nSayfa metni:\n{page_text}",
        }
        result = await self._ask_models(messages, tags, model)
        result.source = "summary"
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
