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


def test_models_endpoint_lists_configured_models():
    client = TestClient(server.app)
    res = client.get("/api/models")
    assert res.status_code == 200
    assert len(res.json()["models"]) > 0


def test_chat_endpoint_uses_assistant(monkeypatch):
    async def fake_ask(self, message, **kwargs):
        return f"echo: {message}"

    monkeypatch.setattr(server.ZenithAssistant, "ask", fake_ask)
    client = TestClient(server.app)
    res = client.post("/api/chat", json={"message": "merhaba"})
    assert res.status_code == 200
    assert res.json()["reply"] == "echo: merhaba"


def test_reset_endpoint_clears_memory(monkeypatch, tmp_path):
    server._assistant.memory.add("user", "hi")
    res = TestClient(server.app).post("/api/reset")
    assert res.status_code == 200
    assert server._assistant.memory.messages == []
