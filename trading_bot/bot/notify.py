"""Telegram bildirimi: bot islem actiginda/kapattiginda telefonuna mesaj atar.

Kurulum (5 dakika, ucretsiz, kimseye para/anahtar verilmez):
 1. Telegram'da @BotFather'a yaz -> /newbot -> isim ver -> sana bir
    TOKEN verir (123456:ABC-... gibi).
 2. Yeni botuna Telegram'dan herhangi bir mesaj at (ör. "selam").
 3. Tarayicida ac: https://api.telegram.org/bot<TOKEN>/getUpdates
    -> cikan JSON'da "chat":{"id":123456789} degerini bul.
 4. Ortam degiskenlerini ayarla:
      TELEGRAM_BOT_TOKEN=123456:ABC-...
      TELEGRAM_CHAT_ID=123456789

Degiskenler yoksa bildirim sessizce atlanir; bot calismaya devam eder.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def discover_chat_ids(token: str = "") -> list[tuple[int, str]]:
    """Bota son 24 saatte yazan sohbetlerin (id, isim) listesini dondurur.

    Kullanim: bota Telegram'dan herhangi bir mesaj at, sonra bunu cagir.
    """
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return []
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=10
        ) as resp:
            data = json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001
        return []
    seen: dict[int, str] = {}
    for update in data.get("result", []):
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            name = chat.get("first_name") or chat.get("title") or chat.get("username") or "?"
            seen[int(chat["id"])] = str(name)
    return list(seen.items())


def send_telegram(text: str) -> bool:
    """Mesaji gonderir; yapilandirma yoksa veya hata olursa False doner.

    Bildirim hatasi asla botu durdurmamali - bu yuzden istisna yutulur.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    try:
        body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return bool(json.loads(resp.read().decode()).get("ok"))
    except Exception:  # noqa: BLE001
        return False
