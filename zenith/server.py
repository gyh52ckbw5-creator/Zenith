"""Zenith icin FastAPI tabanli web/API katmani.

Bu, Zenith'i telefondan (ozellikle iOS Safari'den) bir PWA (Progressive Web
App) olarak kullanabilmeni saglar: sunucuyu calistir, tarayicidan ac,
"Ana Ekrana Ekle" ile gercek bir uygulama gibi telefonuna kur.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .assistant import ZenithAssistant
from .router import NoAvailableModelError

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Zenith")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_assistant = ZenithAssistant()
_lock = asyncio.Lock()  # tek kullanicilik asistan: hafizada yaris durumunu onler


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    council: bool = False
    agent: bool = False  # ajan modu: model araclari kendisi cagirir
    model: str | None = None  # arayuzden secilen model (bos = otomatik)
    system: str | None = None  # istege bagli kisilik/system prompt override
    # Coklu sohbet: istemci o oturumun gecmisini gonderir (sunucu her oturumu
    # kendi tutmaz). Verilirse baglam bundan kurulur, paylasilan hafiza kullanilmaz.
    history: list[ChatMessage] | None = None
    image: str | None = None  # cok-modlu: data: URL olarak gorsel (vision)


class DocRequest(BaseModel):
    name: str
    text: str


class ChatResponse(BaseModel):
    reply: str
    council: bool
    source: str = "model"
    contributors: list[str] = []


@app.get("/api/health")
async def health() -> dict:
    """Deploy sonrasi hizli kontrol: kac model hazir, sistem ayakta mi."""
    available = _assistant.config.available_models()
    return {
        "status": "ok" if available else "no_models",
        "ready_models": [m.name for m in available],
        "hint": (
            None
            if available
            else "Hicbir model hazir degil. Ortam degiskenlerine en az bir ucretsiz "
            "API anahtari ekleyin (onerilen: OPENROUTER_API_KEY, tek anahtarla "
            "Hermes/DeepSeek/Llama gibi onlarca ucretsiz model) ya da yerelde "
            "Ollama calistirin."
        ),
    }


@app.get("/api/models")
async def list_models() -> dict:
    """Hem insan-okur ozet hem de arayuzun model secicisi icin yapisal liste."""
    return {
        "models": _assistant.list_models(),
        "detail": [
            {
                "name": spec.name,
                "provider": spec.provider,
                "priority": spec.priority,
                "tags": list(spec.tags),
                "ready": spec.is_available(),
            }
            for spec in _assistant.config.models
        ],
    }


def _history_payload(payload: ChatRequest) -> list[dict] | None:
    if payload.history is None:
        return None
    return [{"role": m.role, "content": m.content} for m in payload.history]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    async with _lock:
        _assistant.council_mode = payload.council
        _assistant.agent_mode = payload.agent
        try:
            result = await _assistant.ask(
                payload.message,
                model=payload.model,
                system=payload.system,
                history=_history_payload(payload),
                image=payload.image,
            )
        except NoAvailableModelError as exc:
            return ChatResponse(reply=f"[hata] {exc}", council=payload.council, source="error")
    return ChatResponse(
        reply=result.text,
        council=payload.council,
        source=result.source,
        contributors=result.contributors,
    )


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """Cevabi Server-Sent Events (SSE) olarak akitir; her satir bir JSON olay.

    Kilit tum akis boyunca tutulur: paylasilan asistanin hafizasi tek yazar
    olsun ve es zamanli istekler birbirinin akisina karismasin diye.
    """

    async def event_source():
        await _lock.acquire()
        try:
            _assistant.council_mode = payload.council
            _assistant.agent_mode = payload.agent
            async for event in _assistant.ask_stream(
                payload.message,
                model=payload.model,
                system=payload.system,
                history=_history_payload(payload),
                image=payload.image,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except NoAvailableModelError as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': f'[hata] {exc}'}, ensure_ascii=False)}\n\n"
        finally:
            _lock.release()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/docs")
async def add_doc(payload: DocRequest) -> dict:
    """RAG: bir belge (metin) yukler; parcalara bolunup saklanir."""
    async with _lock:
        added = _assistant.docs.add_document(payload.name.strip() or "belge", payload.text)
    return {"ok": True, "chunks": added, "documents": _assistant.docs.documents()}


@app.get("/api/docs")
async def list_docs() -> dict:
    return {"documents": _assistant.docs.documents()}


@app.post("/api/docs/clear")
async def clear_docs() -> dict:
    async with _lock:
        _assistant.docs.clear()
    return {"ok": True}


@app.post("/api/reset")
async def reset() -> dict:
    async with _lock:
        _assistant.memory.reset()
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.json")
async def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.json")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


def run() -> None:
    """`zenith-web` konsol komutu / `python -m zenith web` giris noktasi."""
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("zenith.server:app", host="0.0.0.0", port=port)
