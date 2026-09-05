#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_infrastructure.py
# NG-HEADER: Ubicación: tests/test_meli_infrastructure.py
# NG-HEADER: Descripción: Pruebas estáticas de aislamiento Compose, Cloudflare y Swarm MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_compose_cloudflared_cannot_reach_backend() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "ports" not in services["meli_webhook_gateway"]
    assert set(services["meli_cloudflared"]["networks"]) == {
        "meli_ingress",
        "cloudflare_egress",
    }
    assert "backend" not in services["meli_cloudflared"]["networks"]
    assert "meli_ingress" not in services["meli_sync_worker"]["networks"]
    assert "meli_sync" in services["meli_sync_worker"]["command"]
    for name in ("meli_webhook_gateway", "meli_sync_worker"):
        environment = services[name]["environment"]
        assert environment["OPENAI_API_KEY"] == ""
        assert environment["OPENAI_API_KEY_FILE"] == ""
        assert environment["TELEGRAM_BOT_TOKEN"] == ""
        assert environment["TELEGRAM_BOT_TOKEN_FILE"] == ""


def test_swarm_keeps_meli_replicated_and_secrets_external() -> None:
    stack = yaml.safe_load((ROOT / "docker-stack.yml").read_text(encoding="utf-8"))
    services = stack["services"]
    for name in ("meli_webhook_gateway", "meli_sync_worker", "meli_cloudflared"):
        assert services[name]["deploy"]["replicas"] == 2
        assert services[name]["deploy"]["placement"]["max_replicas_per_node"] == 1
    assert set(services["meli_cloudflared"]["networks"]) == {
        "meli_ingress",
        "cloudflare_egress",
    }
    assert stack["secrets"]["meli_client_secret"]["external"] is True


def test_worker_source_does_not_import_analytic_market_worker() -> None:
    source = (ROOT / "workers" / "meli_sync.py").read_text(encoding="utf-8")
    assert "market_scraping" not in source
    assert 'queue_name="meli_sync"' in source
