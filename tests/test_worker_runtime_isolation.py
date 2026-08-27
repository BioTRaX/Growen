#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_worker_runtime_isolation.py
# NG-HEADER: Ubicación: tests/test_worker_runtime_isolation.py
# NG-HEADER: Descripción: Verifica aislamiento de secretos por dominio en workers.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
NON_TELEGRAM_WORKERS = (
    "dramatiq",
    "market_worker",
    "enrichment_worker",
    "knowledge_worker",
)


def test_non_telegram_workers_disable_telegram_runtime() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    for service_name in NON_TELEGRAM_WORKERS:
        environment = compose["services"][service_name]["environment"]
        assert environment["TELEGRAM_ENABLED"] == "0", service_name
        assert environment["TELEGRAM_PUBLIC_BOT_ENABLED"] == "0", service_name
        assert environment["TELEGRAM_ROLE_LINKING_ENABLED"] == "0", service_name
        assert environment["TELEGRAM_BOT_TOKEN_FILE"] == "", service_name


def test_telegram_worker_keeps_runtime_enabled_by_external_flags() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    environment = compose["services"]["telegram_worker"]["environment"]

    assert environment["TELEGRAM_BOT_TOKEN_FILE"] == "/run/secrets/growen/telegram_bot_token"
    assert "TELEGRAM_ENABLED" not in environment


def test_only_ai_workers_mount_the_openai_secret() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    for service_name in ("dramatiq", "market_worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["OPENAI_API_KEY"] == "", service_name
        assert environment["OPENAI_API_KEY_FILE"] == "", service_name

    for service_name in ("enrichment_worker", "knowledge_worker"):
        service = compose["services"][service_name]
        environment = service["environment"]
        assert environment["OPENAI_API_KEY"] == "", service_name
        assert environment["OPENAI_API_KEY_FILE"] == "/run/secrets/growen/openai_api_key", service_name
        assert any(
            volume.get("target") == "/run/secrets/growen/openai_api_key"
            and volume.get("read_only") is True
            for volume in service["volumes"]
            if isinstance(volume, dict)
        ), service_name
