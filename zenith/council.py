"""Council (konsey) modu: 'tum ucretsiz AI modelleri birlikte calissin'.

Birden fazla ucretsiz model ayni soruyu paralel olarak cevaplar, sonra bir
sentezleyici model bu cevaplarin en iyi yanlarini birlestirip tek bir nihai
cevap uretir. Sentezleyici basarisiz olursa, en yuksek oncelikli basarili
cevap dogrudan dondurulur.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .config import ZenithConfig
from .providers import ModelReply, ProviderError, call_model

SYNTHESIS_SYSTEM_PROMPT = (
    "Sen Zenith'in sentez motorusun. Sana birden fazla yapay zeka modelinin "
    "ayni soruya verdigi cevaplar verilecek. Gorevin: bu cevaplardaki dogru, "
    "faydali ve tamamlayici bilgileri birlestirerek tek, net ve tutarli bir "
    "nihai cevap yazmak. Modeller birbiriyle celisiyorsa en makul olani sec "
    "ve neden sectigini kisaca belirt. Modellerin isimlerini cevaba katma, "
    "sadece nihai, dogal bir cevap uret."
)


@dataclass
class CouncilResult:
    final_answer: str
    contributors: list[ModelReply]
    synthesizer: str | None
    failed: list[str]


async def _gather_opinions(
    config: ZenithConfig, messages: list[dict], tags: tuple[str, ...]
) -> tuple[list[ModelReply], list[str]]:
    candidates = config.models_for_tags(tags)[: config.council_max_parallel]
    tasks = [call_model(spec, messages) for spec in candidates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    opinions: list[ModelReply] = []
    failed: list[str] = []
    for spec, result in zip(candidates, results):
        if isinstance(result, Exception):
            failed.append(spec.name)
        else:
            opinions.append(result)
    return opinions, failed


def _build_synthesis_messages(user_question: str, opinions: list[ModelReply]) -> list[dict]:
    opinions_text = "\n\n".join(
        f"### Model {i + 1} cevabi\n{op.content}" for i, op in enumerate(opinions)
    )
    return [
        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Kullanicinin sorusu:\n{user_question}\n\nModellerin cevaplari:\n{opinions_text}",
        },
    ]


async def ask(
    config: ZenithConfig,
    messages: list[dict],
    *,
    tags: tuple[str, ...] = (),
) -> CouncilResult:
    opinions, failed = await _gather_opinions(config, messages, tags)

    if not opinions:
        raise RuntimeError(
            f"Konsey icin hicbir model cevap vermedi. Basarisiz olanlar: {', '.join(failed) or 'yok'}"
        )

    if len(opinions) == 1:
        return CouncilResult(
            final_answer=opinions[0].content,
            contributors=opinions,
            synthesizer=None,
            failed=failed,
        )

    user_question = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    synth_candidates = config.models_for_tags(config.synthesizer_tags)
    synth_spec = synth_candidates[0] if synth_candidates else None

    if synth_spec is not None:
        try:
            synthesis = await call_model(
                synth_spec, _build_synthesis_messages(user_question, opinions)
            )
            return CouncilResult(
                final_answer=synthesis.content,
                contributors=opinions,
                synthesizer=synth_spec.name,
                failed=failed,
            )
        except ProviderError:
            pass

    # Sentez basarisiz olduysa, en yuksek oncelikli (ilk giden) cevaba dus.
    return CouncilResult(
        final_answer=opinions[0].content,
        contributors=opinions,
        synthesizer=None,
        failed=failed,
    )
