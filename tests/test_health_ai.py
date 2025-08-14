from fastapi.testclient import TestClient

from services.api import app
from ai.providers.ollama_provider import OllamaProvider
from ai.providers.openai_provider import OpenAIProvider


def test_health_ai(monkeypatch):
    async def ok(self):
        return {"ok": True, "detail": "ok"}

    monkeypatch.setattr(OllamaProvider, "healthcheck", ok)
    monkeypatch.setattr(OpenAIProvider, "healthcheck", ok)

    client = TestClient(app)
    r = client.get("/health/ai")
    assert r.status_code == 200
    data = r.json()
    assert data["ollama"]["ok"]
    assert data["openai"]["ok"]
