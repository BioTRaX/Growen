import os

from ai.policy import choose_provider


def test_policy_fallback_to_ollama_when_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "x")
    monkeypatch.setenv("OLLAMA_MODEL", "y")
    assert choose_provider("short_answer", {}) == "ollama"


def test_policy_use_openai_when_no_ollama(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert choose_provider("short_answer", {}) == "openai"


def test_policy_dev_offline(monkeypatch):
    monkeypatch.setenv("ENV", "dev_offline")
    assert choose_provider("content.generation", {}) == "ollama"
