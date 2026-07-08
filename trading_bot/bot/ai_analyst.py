"""Ucretsiz yapay zeka yorumcusu (istege bagli).

Tarama sonuclarini OpenRouter uzerindeki UCRETSIZ bir modele gonderir ve
temkinli bir risk yoneticisi agziyla kisa Turkce yorum alir.

Kurulum (ucretsiz):
 1. https://openrouter.ai -> kayit ol -> Keys -> yeni anahtar olustur
 2. trading_bot/.env dosyasina ekle: OPENROUTER_API_KEY=sk-or-...
 3. Istege bagli model secimi: AI_MODEL=deepseek/deepseek-chat-v3-0324:free

Anahtar yoksa modul sessizce devre disi kalir; bot normal calisir.
ONEMLI: AI yorumu da tahmindir, emir/karar mercii DEGILDIR - son soz
her zaman risk kurallarinindir.
"""

from __future__ import annotations

import json
import os
import urllib.request

_SYSTEM_PROMPT = (
    "Sen temkinli bir portfoy risk yoneticisisin. Sana bir trading botunun "
    "tarama/analiz ozeti verilecek. 3-4 cumleyle Turkce yorumla: neye dikkat "
    "edilmeli, hangi sonuc supheli olabilir, acele etmemek icin bir neden soyle. "
    "ASLA kesin kazanc vaat etme, 'kesinlikle al/sat' deme. Kisa ve net ol."
)


def ai_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def ai_comment(summary: str) -> str | None:
    """Analiz ozetine AI yorumu dondurur; anahtar yoksa/hata olursa None."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return None
    model = os.environ.get("AI_MODEL", "deepseek/deepseek-chat-v3-0324:free")
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": summary[:6000]},
            ],
            "max_tokens": 400,
        }
    ).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"].strip()
    except Exception:  # noqa: BLE001 - yorum alinamazsa bot durmasin
        return None
