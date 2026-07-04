"""Zenith icin interaktif komut satiri arayuzu."""

from __future__ import annotations

import asyncio

from .assistant import ZenithAssistant
from .router import NoAvailableModelError

BANNER = """
Zenith - kisisel yapay zeka asistanin
Komutlar:
  /council   - konsey modunu ac/kapa (birden fazla model birlikte cevaplar)
  /models    - yapilandirilmis modelleri ve durumlarini listele
  /reset     - konusma hafizasini temizle
  /exit      - cikis

Yetenekler (dogrudan yaz):
  hesapla: 12*7        wiki: kuantum fizigi     hava: Istanbul
  kur: 100 dolar tl    ara: bugun ne oldu        ozetle: <url>
  haber: ekonomi       sozluk: serendipity       sifre: 20
  not: sut al          notlarim / not sil 1      kullanici: <ad>
"""


async def _run() -> None:
    assistant = ZenithAssistant()
    print(BANNER)

    while True:
        try:
            user_input = input("sen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGorusuruz!")
            return

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            print("Gorusuruz!")
            return
        if user_input == "/reset":
            assistant.memory.reset()
            print("Hafiza temizlendi.")
            continue
        if user_input == "/models":
            print("\n".join(assistant.list_models()))
            continue
        if user_input == "/council":
            assistant.council_mode = not assistant.council_mode
            state = "acik" if assistant.council_mode else "kapali"
            print(f"Konsey modu: {state}")
            continue

        try:
            result = await assistant.ask(user_input)
        except NoAvailableModelError as exc:
            print(f"[hata] {exc}")
            continue

        print(f"zenith> {result.text}")
        if result.source == "council" and result.contributors:
            print(f"        (konsey: {', '.join(result.contributors)})")
        print()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
