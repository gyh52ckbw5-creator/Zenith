import pytest

from zenith import router
from zenith.config import ModelSpec, ZenithConfig
from zenith.providers import ModelReply, ProviderError


def make_config(*specs: ModelSpec) -> ZenithConfig:
    return ZenithConfig(models=specs, council_max_parallel=4, synthesizer_tags=("reasoning",))


@pytest.mark.asyncio
async def test_ask_returns_first_successful_model(monkeypatch):
    spec_a = ModelSpec("a", "provider/a", "provider", None, (), priority=1)
    spec_b = ModelSpec("b", "provider/b", "provider", None, (), priority=2)
    config = make_config(spec_a, spec_b)

    async def fake_call_model(spec, messages, **kwargs):
        return ModelReply(model_name=spec.name, litellm_id=spec.litellm_id, content=f"reply-from-{spec.name}")

    monkeypatch.setattr(router, "call_model", fake_call_model)

    reply = await router.ask(config, [{"role": "user", "content": "hi"}])
    assert reply.model_name == "a"
    assert reply.content == "reply-from-a"


@pytest.mark.asyncio
async def test_ask_falls_back_on_failure(monkeypatch):
    spec_a = ModelSpec("a", "provider/a", "provider", None, (), priority=1)
    spec_b = ModelSpec("b", "provider/b", "provider", None, (), priority=2)
    config = make_config(spec_a, spec_b)

    async def fake_call_model(spec, messages, **kwargs):
        if spec.name == "a":
            raise ProviderError("a", Exception("boom"))
        return ModelReply(model_name=spec.name, litellm_id=spec.litellm_id, content="ok-from-b")

    monkeypatch.setattr(router, "call_model", fake_call_model)

    reply = await router.ask(config, [{"role": "user", "content": "hi"}])
    assert reply.model_name == "b"


@pytest.mark.asyncio
async def test_ask_raises_when_all_models_fail(monkeypatch):
    spec_a = ModelSpec("a", "provider/a", "provider", None, (), priority=1)
    config = make_config(spec_a)

    async def fake_call_model(spec, messages, **kwargs):
        raise ProviderError(spec.name, Exception("boom"))

    monkeypatch.setattr(router, "call_model", fake_call_model)

    with pytest.raises(router.NoAvailableModelError):
        await router.ask(config, [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_ask_raises_when_no_models_configured():
    config = make_config()
    with pytest.raises(router.NoAvailableModelError):
        await router.ask(config, [{"role": "user", "content": "hi"}])
