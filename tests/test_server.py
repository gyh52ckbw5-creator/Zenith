from fastapi.testclient import TestClient

from zenith import server


def test_index_serves_pwa_shell():
    client = TestClient(server.app)
    res = client.get("/")
    assert res.status_code == 200
    assert "Zenith" in res.text


def test_manifest_has_ios_friendly_icons():
    client = TestClient(server.app)
    res = client.get("/manifest.json")
    assert res.status_code == 200
    data = res.json()
    sizes = {icon["sizes"] for icon in data["icons"]}
    assert "180x180" in sizes  # iOS apple-touch-icon boyutu


def test_health_reports_no_models_without_keys(monkeypatch):
    monkeypatch.setenv("ZENITH_DISABLE_OLLAMA", "1")
    for key in (
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "CEREBRAS_API_KEY",
        "GITHUB_API_KEY",
        "MISTRAL_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    res = TestClient(server.app).get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "no_models"
    assert "OPENROUTER_API_KEY" in data["hint"]


def test_health_ok_when_a_key_is_present(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    res = TestClient(server.app).get("/api/health")
    data = res.json()
    assert data["status"] == "ok"
    assert any("groq" in name for name in data["ready_models"])


def test_models_endpoint_lists_configured_models():
    client = TestClient(server.app)
    res = client.get("/api/models")
    assert res.status_code == 200
    assert len(res.json()["models"]) > 0


def test_chat_endpoint_uses_assistant(monkeypatch):
    from zenith.assistant import AskResult

    async def fake_ask(self, message, **kwargs):
        return AskResult(text=f"echo: {message}", source="council", contributors=["a", "b"])

    monkeypatch.setattr(server.ZenithAssistant, "ask", fake_ask)
    client = TestClient(server.app)
    res = client.post("/api/chat", json={"message": "merhaba"})
    assert res.status_code == 200
    data = res.json()
    assert data["reply"] == "echo: merhaba"
    assert data["source"] == "council"
    assert data["contributors"] == ["a", "b"]


def test_reset_endpoint_clears_memory(monkeypatch, tmp_path):
    server._assistant.memory.add("user", "hi")
    res = TestClient(server.app).post("/api/reset")
    assert res.status_code == 200
    assert server._assistant.memory.messages == []
