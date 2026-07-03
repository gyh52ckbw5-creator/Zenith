import pytest

from zenith import council
from zenith.config import ModelSpec, ZenithConfig
from zenith.providers import ModelReply, ProviderError


def make_config(*specs: ModelSpec, synthesizer_tags=("reasoning",)) -> ZenithConfig:
    return ZenithConfig(models=specs, council_max_parallel=4, synthesizer_tags=synthesizer_tags)


@pytest.mark.asyncio
async def test_council_synthesizes_multiple_opinions(monkeypatch):
    spec_a = ModelSpec("a", "p/a", "p", None, (), priority=1)
    spec_b = ModelSpec("b", "p/b", "p", None, (), priority=2)
    synth = ModelSpec("synth", "p/synth", "p", None, ("reasoning",), priority=3)
    config = make_config(spec_a, spec_b, synth)

    async def fake_call_model(spec, messages, **kwargs):
        if spec.name == "synth":
            return ModelReply(spec.name, spec.litellm_id, "final-merged-answer")
        return ModelReply(spec.name, spec.litellm_id, f"opinion-from-{spec.name}")

    monkeypatch.setattr(council, "call_model", fake_call_model)

    result = await council.ask(config, [{"role": "user", "content": "hi"}])
    assert result.final_answer == "final-merged-answer"
    assert result.synthesizer == "synth"
    assert len(result.contributors) == 3


@pytest.mark.asyncio
async def test_council_falls_back_to_best_opinion_if_synthesis_fails(monkeypatch):
    spec_a = ModelSpec("a", "p/a", "p", None, (), priority=1)
    spec_b = ModelSpec("b", "p/b", "p", None, (), priority=2)
    synth = ModelSpec("synth", "p/synth", "p", None, ("reasoning",), priority=3)
    config = make_config(spec_a, spec_b, synth)

    async def fake_call_model(spec, messages, **kwargs):
        if spec.name == "synth":
            raise ProviderError("synth", Exception("down"))
        return ModelReply(spec.name, spec.litellm_id, f"opinion-from-{spec.name}")

    monkeypatch.setattr(council, "call_model", fake_call_model)

    result = await council.ask(config, [{"role": "user", "content": "hi"}])
    assert result.synthesizer is None
    assert result.final_answer.startswith("opinion-from-")


@pytest.mark.asyncio
async def test_council_raises_if_all_models_fail(monkeypatch):
    spec_a = ModelSpec("a", "p/a", "p", None, (), priority=1)
    config = make_config(spec_a)

    async def fake_call_model(spec, messages, **kwargs):
        raise ProviderError(spec.name, Exception("down"))

    monkeypatch.setattr(council, "call_model", fake_call_model)

    with pytest.raises(RuntimeError):
        await council.ask(config, [{"role": "user", "content": "hi"}])
