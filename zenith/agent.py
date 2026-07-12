"""Ajan modu: fonksiyon cagirma (tool use) dongusu.

Guvenilir yerlesik 'function calling' her ucretsiz saglayicida ayni sekilde
calismadigi icin, saglayicidan bagimsiz basit bir protokol kullanilir:
model her adimda ya bir arac cagirir ya da nihai cevabi verir.

  ARAC: arac_adi | arguman

satirini gorursek araci calistirip sonucu modele geri veririz; model
GOZLEM'i gorup ya baska arac cagirir ya da:

  CEVAP: nihai cevap

yazar. Bu, ReAct desenli hafif bir ajandir.
"""

from __future__ import annotations

import asyncio
import re

from . import skills, tools, trading_tools, websearch
from .config import ZenithConfig
from .router import ask as router_ask

MAX_STEPS = 4


def _threaded(fn):
    """Senkron (ag/CPU isi yapan) araci ajanin async dongusune uyarlar."""

    async def inner(arg: str) -> str:
        try:
            return await asyncio.to_thread(fn, arg)
        except Exception as exc:  # noqa: BLE001 - arac hatasi ajani oldurmesin
            return f"arac hatasi: {exc}"

    return inner


async def _run_search(query: str) -> str:
    try:
        results = await websearch.search(query, max_results=4)
    except websearch.SearchError as exc:
        return f"arama hatasi: {exc}"
    return websearch.format_results(results)


# Ajanin kullanabilecegi araclar: ad -> (async fonksiyon, aciklama).
TOOLS = {
    "wiki": (skills.wikipedia, "Bir konuda Wikipedia ozeti getirir. Arguman: konu."),
    "hava": (skills.weather, "Bir sehrin guncel hava durumu. Arguman: sehir."),
    "kur": (skills.currency, "Doviz cevirir. Arguman: '100 USD TRY' gibi."),
    "haber": (skills.news, "Guncel haber basliklari. Arguman: konu (bos olabilir)."),
    "sozluk": (skills.dictionary, "Ingilizce kelime tanimi. Arguman: kelime."),
    "ara": (_run_search, "Web'de arar. Arguman: sorgu."),
    # Trading araclari (trading_bot koprusu) - egitim amacli, gercek emir yok:
    "fiyat": (_threaded(tools.price_lookup),
              "Guncel fiyat. Arguman: sembol (BTCUSDT, EURUSD, XAUUSD...)."),
    "piyasa": (_threaded(tools.market_scan),
               "Piyasa taramasi: strateji kombinasyonlarini dener, en iyileri verir. "
               "Arguman: virgullu semboller veya FOREX/KRIPTO/HEPSI (bos olabilir)."),
    "backtest": (_threaded(trading_tools.backtest_text),
                 "Stratejiyi gecmis veride test eder. Arguman: 'SEMBOL strateji periyot' "
                 "(ör: 'XAUUSD sma 1d'; stratejiler: sma ema rsi donchian bollinger macd)."),
    "walkforward": (_threaded(trading_tools.walkforward_text),
                    "Stratejiyi ardisik donemlerde dogrular (guvenilirlik testi). "
                    "Arguman: 'SEMBOL strateji periyot'."),
    "optimize": (_threaded(trading_tools.optimize_text),
                 "Strateji parametrelerini walk-forward puaniyla arar. "
                 "Arguman: 'SEMBOL strateji periyot'."),
    "portfoy": (_threaded(trading_tools.portfolio_text),
                "Calisan trading botunun sanal portfoy durumu. Arguman: bos."),
    "derin": (_threaded(trading_tools.deep_report_text),
              "Tek sembol DERIN analiz: rejim (ADX), trend, momentum, oynaklik, "
              "destek/direnc, strateji onerisi. Arguman: 'SEMBOL [periyot]' (ör. 'XAUUSD 1d')."),
    "montecarlo": (_threaded(trading_tools.montecarlo_text),
                   "Backtest sonucunun ne kadar SANSA bagli oldugunu binlerce simulasyonla "
                   "olcer (getiri araligi, kotu-sans drawdown, iflas olasiligi). "
                   "Arguman: 'SEMBOL strateji periyot'."),
}


def _system_prompt() -> str:
    lines = "\n".join(f"- {name}: {desc}" for name, (_, desc) in TOOLS.items())
    return (
        "Sen Zenith'in arac kullanan ajanisin. Kullanicinin sorusunu cevaplamak "
        "icin gerektiginde asagidaki araclari cagirabilirsin.\n\n"
        f"Araclar:\n{lines}\n\n"
        "Bir arac kullanmak istersen SADECE su formatta tek satir yaz:\n"
        "ARAC: arac_adi | arguman\n\n"
        "Arac sonucunu GOZLEM olarak alacaksin. Yeterince bilgin olunca su "
        "formatta bitir:\n"
        "CEVAP: <nihai cevabin>\n\n"
        "Arac gerekmiyorsa dogrudan 'CEVAP: ...' yaz. Ayni araci gereksiz yere "
        "tekrar cagirma."
    )


_TOOL_RE = re.compile(r"ARAC\s*:\s*([\w]+)\s*\|\s*(.*)", re.IGNORECASE)
_ANSWER_RE = re.compile(r"CEVAP\s*:\s*(.+)", re.IGNORECASE | re.DOTALL)


async def run(
    config: ZenithConfig,
    user_question: str,
    *,
    model: str | None = None,
    max_steps: int = MAX_STEPS,
) -> tuple[str, list[str]]:
    """Ajani calistirir. (nihai_cevap, kullanilan_araclar) dondurur."""
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": user_question},
    ]
    used: list[str] = []

    for _ in range(max_steps):
        reply = await router_ask(config, messages, tags=("reasoning",), preferred=model)
        content = reply.content.strip()
        messages.append({"role": "assistant", "content": content})

        answer = _ANSWER_RE.search(content)
        tool = _TOOL_RE.search(content)
        # 'CEVAP:' varsa ve arac cagrisindan once/tek basinaysa bitir.
        if answer and (not tool or answer.start() < tool.start()):
            return answer.group(1).strip(), used

        if tool:
            name = tool.group(1).lower()
            arg = tool.group(2).strip()
            handler = TOOLS.get(name, (None, None))[0]
            if handler is None:
                observation = f"Bilinmeyen arac: {name}"
            else:
                used.append(name)
                observation = await handler(arg)
            messages.append({"role": "user", "content": f"GOZLEM: {observation}"})
            continue

        # Ne arac ne de bicimli cevap - ham metni cevap say.
        return content, used

    # Adim limiti: son bir kez cevap iste.
    messages.append(
        {"role": "user", "content": "Eldeki bilgiyle 'CEVAP: ...' formatinda bitir."}
    )
    reply = await router_ask(config, messages, tags=("reasoning",), preferred=model)
    answer = _ANSWER_RE.search(reply.content)
    return (answer.group(1).strip() if answer else reply.content.strip()), used
