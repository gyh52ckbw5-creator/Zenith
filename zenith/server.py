"""Zenith icin FastAPI tabanli web/API katmani.

Bu, Zenith'i telefondan (ozellikle iOS Safari'den) bir PWA (Progressive Web
App) olarak kullanabilmeni saglar: sunucuyu calistir, tarayicidan ac,
"Ana Ekrana Ekle" ile gercek bir uygulama gibi telefonuna kur.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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


class ChatRequest(BaseModel):
    message: str
    council: bool = False


class ChatResponse(BaseModel):
    reply: str
    council: bool


@app.get("/api/models")
async def list_models() -> dict:
    return {"models": _assistant.list_models()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    async with _lock:
        _assistant.council_mode = payload.council
        try:
            reply = await _assistant.ask(payload.message)
        except NoAvailableModelError as exc:
            reply = f"[hata] {exc}"
    return ChatResponse(reply=reply, council=payload.council)


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
