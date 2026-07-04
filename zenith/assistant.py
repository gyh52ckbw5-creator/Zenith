"""ZenithAssistant: hafiza, yerel araclar, web aramasi, tek-model router'i ve
konsey modunu bir araya getiren ana kisilik/orkestrasyon katmani."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import agent, council, rag, router, skills, tools, websearch
from .config import ZenithConfig, load_config
from .memory import ConversationMemory
from .notes import NotesStore
from .profile import ProfileStore
from .rag import DocStore

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

# --- Profil (uzun sureli hafiza) ---
PROFILE_ADD_PATTERN = re.compile(
    r"^\s*(?:beni hatirla|beni hatırla|profil ekle|remember)\s*[:=]\s*(.+)$", re.IGNORECASE
)
PROFILE_LIST_PATTERN = re.compile(r"^\s*(?:profilim|profil|hakkimda)\s*$", re.IGNORECASE)
PROFILE_CLEAR_PATTERN = re.compile(r"^\s*profil(?:i|imi)?\s+temizle\s*$", re.IGNORECASE)

# --- Belgeler (RAG) ---
DOCS_LIST_PATTERN = re.compile(r"^\s*(?:belgelerim|belgeler|documents)\s*$", re.IGNORECASE)
DOCS_CLEAR_PATTERN = re.compile(r"^\s*belgeler(?:i|imi)?\s+temizle\s*$", re.IGNORECASE)

RAG_PROMPT = (
    "Asagida kullanicinin kendi belgelerinden ilgili bolumler var. Soruyu "
    "ONCELIKLE bu bolumlere dayanarak cevapla; belge yetersizse bunu belirt "
    "ve genel bilgiyle tamamla. Hangi belgeden yararlandiginsa belirt."
)


@dataclass
class AskResult:
    """Bir sorunun cevabi + nasil uretildigine dair meta bilgi."""

    text: str
    # "local"|"model"|"council"|"search"|"skill"|"summary"|"agent"|"rag"
    source: str = "model"
    contributors: list[str] = field(default_factory=list)


class ZenithAssistant:
    def __init__(
        self,
        config: ZenithConfig | None = None,
        memory: ConversationMemory | None = None,
        council_mode: bool = False,
        notes: NotesStore | None = None,
        profile: ProfileStore | None = None,
        docs: DocStore | None = None,
        agent_mode: bool = False,
    ):
        self.config = config or load_config()
        self.memory = memory if memory is not None else ConversationMemory()
        self.council_mode = council_mode
        self.agent_mode = agent_mode
        self.notes = notes if notes is not None else NotesStore()
        self.profile = profile if profile is not None else ProfileStore()
        self.docs = docs if docs is not None else DocStore()

    def _effective_system(self, system: str | None) -> str:
        """Temel kisilige uzun sureli hafizayi (profil) ekler."""
        return (system or system_prompt()) + self.profile.as_prompt()

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

    def _handle_profile(self, user_input: str) -> str | None:
        add = PROFILE_ADD_PATTERN.match(user_input)
        if add:
            self.profile.add(add.group(1).strip())
            return "Tamam, bunu senin hakkinda hatirlayacagim (her sohbette)."

        if PROFILE_LIST_PATTERN.match(user_input):
            facts = self.profile.list()
            if not facts:
                return "Henuz senin hakkinda bir sey hatirlamiyorum. 'beni hatirla: ...' de."
            return "**Senin hakkinda hatirladiklarim:**\n" + "\n".join(f"- {f}" for f in facts)

        if PROFILE_CLEAR_PATTERN.match(user_input):
            self.profile.clear()
            return "Profil hafizasi temizlendi."

        return None

    def _handle_docs(self, user_input: str) -> str | None:
        if DOCS_LIST_PATTERN.match(user_input):
            names = self.docs.documents()
            if not names:
                return "Henuz belge yuklemedin. Arayuzden bir metin/PDF-metni yukleyebilirsin."
            return "**Yuklu belgelerin:**\n" + "\n".join(f"- {n}" for n in names)

        if DOCS_CLEAR_PATTERN.match(user_input):
            self.docs.clear()
            return "Tum belgeler silindi."

        return None

    async def ask(
        self,
        user_input: str,
        *,
        tags: tuple[str, ...] = (),
        model: str | None = None,
        system: str | None = None,
        history: list[dict] | None = None,
        image: str | None = None,
    ) -> AskResult:
        result = await self._resolve_non_streaming(
            user_input, tags, model, system, history, image
        )
        if result is not None:
            return result

        # Duz model yolu (konsey degil): tek seferde topla.
        use_tags = tags + ("vision",) if image else tags
        messages = self._compose(user_input, system, history, image)
        reply = await router.ask(self.config, messages, tags=use_tags, preferred=model)
        self._persist_reply(history, reply.content)
        return AskResult(text=reply.content, source="model", contributors=[reply.model_name])

    async def ask_stream(
        self,
        user_input: str,
        *,
        tags: tuple[str, ...] = (),
        model: str | None = None,
        system: str | None = None,
        history: list[dict] | None = None,
        image: str | None = None,
    ):
        """`ask` ile ayni yollari izler; duz model yolunda cevabi token token
        akitir. Her adimda bir olay sozlugu uretir:
          {"type":"delta","text":...} | {"type":"meta",...} | {"type":"done"}
        """
        result = await self._resolve_non_streaming(
            user_input, tags, model, system, history, image
        )
        if result is not None:
            yield {"type": "delta", "text": result.text}
            yield {"type": "meta", "source": result.source, "contributors": result.contributors}
            yield {"type": "done"}
            return

        use_tags = tags + ("vision",) if image else tags
        messages = self._compose(user_input, system, history, image)
        chunks: list[str] = []
        model_name: str | None = None
        async for kind, value in router.ask_stream(
            self.config, messages, tags=use_tags, preferred=model
        ):
            if kind == "model":
                model_name = value
            else:
                chunks.append(value)
                yield {"type": "delta", "text": value}

        text = "".join(chunks).strip()
        self._persist_reply(history, text)
        yield {
            "type": "meta",
            "source": "model",
            "contributors": [model_name] if model_name else [],
        }
        yield {"type": "done"}

    def _compose(
        self, user_input: str, system: str | None, history: list[dict] | None, image: str | None
    ) -> list[dict]:
        """Model'e gidecek mesaj listesini kurar.

        history verilirse (web/coklu-oturum): [system] + history + [kullanici];
        hafizaya YAZMAZ (istemci her oturumu kendi saklar).
        history yoksa (CLI): paylasilan hafizayi kullanir ve kullaniciyi ekler.
        image varsa kullanici mesaji cok-modlu (metin + gorsel) olur.
        """
        sys = self._effective_system(system)
        content: object = user_input
        if image:
            content = [
                {"type": "text", "text": user_input or "Bu gorseli acikla."},
                {"type": "image_url", "image_url": {"url": image}},
            ]
        if history is not None:
            return [{"role": "system", "content": sys}, *history, {"role": "user", "content": content}]

        self.memory.add("user", user_input)
        messages = self.memory.as_messages(sys)
        if image:
            messages[-1] = {"role": "user", "content": content}
        return messages

    def _persist_reply(self, history: list[dict] | None, reply: str) -> None:
        if history is None:
            self.memory.add("assistant", reply)

    async def _resolve_non_streaming(
        self,
        user_input: str,
        tags: tuple[str, ...],
        model: str | None,
        system: str | None,
        history: list[dict] | None = None,
        image: str | None = None,
    ) -> AskResult | None:
        """Akitilamayan (tam sonuc donen) yollari isler: yerel arac, yetenek,
        ozetleme, arama, konsey. Duz model yolu icin None doner (akitilacak).

        Gorsel varsa tum metin-komut yollari atlanir; dogrudan vision modeline gider.
        """
        if image:
            return None

        local_reply = tools.try_handle_locally(user_input)
        if local_reply is not None:
            self._remember(user_input, local_reply, history)
            return AskResult(text=local_reply, source="local")

        note_reply = self._handle_notes(user_input)
        if note_reply is not None:
            self._remember(user_input, note_reply, history)
            return AskResult(text=note_reply, source="skill")

        profile_reply = self._handle_profile(user_input)
        if profile_reply is not None:
            self._remember(user_input, profile_reply, history)
            return AskResult(text=profile_reply, source="skill")

        docs_reply = self._handle_docs(user_input)
        if docs_reply is not None:
            self._remember(user_input, docs_reply, history)
            return AskResult(text=docs_reply, source="skill")

        for pattern, handler_name in _DIRECT_SKILLS:
            match = pattern.match(user_input)
            if match:
                handler = getattr(skills, handler_name)
                reply = await handler(match.group(1).strip())
                self._remember(user_input, reply, history)
                return AskResult(text=reply, source="skill")

        summarize_match = SUMMARIZE_PATTERN.match(user_input)
        if summarize_match:
            return await self._ask_with_summary(
                user_input, summarize_match.group(1), tags, model, system, history
            )

        search_match = SEARCH_PATTERN.match(user_input)
        if search_match:
            return await self._ask_with_search(
                user_input, search_match.group(1), tags, model, system, history
            )

        # Ajan modu: model gerektiginde araclari kendisi cagirir.
        if self.agent_mode:
            answer, used = await agent.run(self.config, user_input, model=model)
            self._remember(user_input, answer, history)
            return AskResult(text=answer, source="agent", contributors=used)

        # RAG: kullanici belge yuklediyse, ilgili bolumleri baglama kat.
        if not self.docs.is_empty():
            chunks = self.docs.retrieve(user_input)
            if chunks:
                context = rag.DocStore.format_context(chunks)
                prompt = f"{RAG_PROMPT}\n\nBelge bolumleri:\n{context}\n\nSoru: {user_input}"
                messages = self._context_with_prompt(user_input, system, history, prompt)
                result = await self._ask_models(messages, tags, model)
                result.source = "rag"
                self._persist_reply(history, result.text)
                return result

        if self.council_mode:
            messages = self._compose(user_input, system, history, None)
            result = await self._ask_models(messages, tags, model)
            self._persist_reply(history, result.text)
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

    def _context_with_prompt(
        self, user_input: str, system: str | None, history: list[dict] | None, prompt: str
    ) -> list[dict]:
        """Bir gecici 'prompt' (arama/ozet baglami) iceren kullanici mesajiyla
        birlikte model'e gidecek mesaj listesini kurar. Ham baglam hafizaya
        yazilmaz; memory modunda gercek kullanici girdisi ayrica saklanir."""
        sys = self._effective_system(system)
        if history is not None:
            return [{"role": "system", "content": sys}, *history, {"role": "user", "content": prompt}]
        self.memory.add("user", user_input)
        messages = self.memory.as_messages(sys)
        messages[-1] = {"role": "user", "content": prompt}
        return messages

    async def _ask_with_search(
        self,
        user_input: str,
        query: str,
        tags: tuple[str, ...],
        model: str | None = None,
        system: str | None = None,
        history: list[dict] | None = None,
    ) -> AskResult:
        try:
            results = await websearch.search(query)
        except websearch.SearchError as exc:
            text = f"[arama hatasi] {exc}"
            self._remember(user_input, text, history)
            return AskResult(text=text, source="search")

        findings = websearch.format_results(results)
        prompt = f"{SEARCH_ANSWER_PROMPT}\n\nSorgu: {query}\n\nArama sonuclari:\n{findings}"
        messages = self._context_with_prompt(user_input, system, history, prompt)
        result = await self._ask_models(messages, tags, model)
        result.source = "search"
        self._persist_reply(history, result.text)
        return result

    async def _ask_with_summary(
        self,
        user_input: str,
        url: str,
        tags: tuple[str, ...],
        model: str | None = None,
        system: str | None = None,
        history: list[dict] | None = None,
    ) -> AskResult:
        try:
            page_text = await skills.fetch_page_text(url)
        except skills.SkillError as exc:
            text = f"[ozetleme hatasi] {exc}"
            self._remember(user_input, text, history)
            return AskResult(text=text, source="summary")

        if not page_text.strip():
            text = "Sayfadan metin cikarilamadi (bos ya da JS ile yuklenen icerik)."
            self._remember(user_input, text, history)
            return AskResult(text=text, source="summary")

        prompt = f"{SUMMARIZE_PROMPT}\n\nKaynak: {url}\n\nSayfa metni:\n{page_text}"
        messages = self._context_with_prompt(user_input, system, history, prompt)
        result = await self._ask_models(messages, tags, model)
        result.source = "summary"
        self._persist_reply(history, result.text)
        return result

    def _remember(self, user_input: str, reply: str, history: list[dict] | None = None) -> None:
        if history is None:
            self.memory.add("user", user_input)
            self.memory.add("assistant", reply)

    def list_models(self) -> list[str]:
        lines = []
        for spec in self.config.models:
            status = "hazir" if spec.is_available() else "anahtar/lokal eksik"
            lines.append(f"- {spec.name} ({spec.provider}, oncelik={spec.priority}): {status}")
        return lines
