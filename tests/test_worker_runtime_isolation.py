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
    "catalog_audit_worker",
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


def test_catalog_audit_compose_service_has_no_global_container_name() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert "container_name" not in compose["services"]["catalog_audit_worker"]


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

    audit_environment = compose["services"]["catalog_audit_worker"]["environment"]
    assert audit_environment["OPENAI_API_KEY"] == ""
    assert audit_environment["OPENAI_API_KEY_FILE"] == ""

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


def test_compose_defaults_keep_development_data_separate_from_swarm() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert compose["volumes"]["pgdata"]["name"] == "${COMPOSE_PGDATA_VOLUME:-growen_dev_pgdata}"
    assert compose["volumes"]["redis_data"]["name"] == "${COMPOSE_REDIS_DATA_VOLUME:-growen_dev_redis_data}"
    assert compose["networks"]["backend"]["name"] == "${COMPOSE_BACKEND_NETWORK:-growen_dev_backend}"
    assert compose["networks"]["host_access"]["name"] == "${COMPOSE_HOST_ACCESS_NETWORK:-growen_dev_host_access}"


def test_worker_lock_ignores_windows_only_packages_on_linux() -> None:
    lock = (ROOT / "requirements-worker-lock.txt").read_text(encoding="utf-8")

    assert 'pywin32==312 ; sys_platform == "win32" \\' in lock
    assert 'python-magic-bin==0.4.14 ; platform_system == "Windows" \\' in lock
    assert '# via -r requirements-base.txtpython-magic-bin' not in lock
