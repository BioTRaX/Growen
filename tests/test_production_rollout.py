#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_production_rollout.py
# NG-HEADER: Ubicación: tests/test_production_rollout.py
# NG-HEADER: Descripción: Valida contratos fail-closed del rollout productivo LAN.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Pruebas estáticas y unitarias de la infraestructura productiva."""

from __future__ import annotations

import importlib.util
import ipaddress
from pathlib import Path
import shutil
import subprocess

from cryptography import x509
from cryptography.hazmat.primitives import serialization
import yaml


ROOT = Path(__file__).resolve().parents[1]
IMAGE_VARIABLES = {
    "GROWEN_POSTGRES_IMAGE",
    "GROWEN_REDIS_IMAGE",
    "GROWEN_API_IMAGE",
    "GROWEN_FRONTEND_IMAGE",
    "GROWEN_TELEGRAM_IMAGE",
    "GROWEN_DRAMATIQ_IMAGE",
    "GROWEN_MARKET_WORKER_IMAGE",
    "GROWEN_MCP_PRODUCTS_IMAGE",
    "GROWEN_MCP_WEB_SEARCH_IMAGE",
    "GROWEN_SIYUAN_IMAGE",
    "GROWEN_MCP_SIYUAN_IMAGE",
    "GROWEN_MELI_IMAGE",
    "GROWEN_CLOUDFLARED_IMAGE",
}


def _yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _load_alembic_runner():
    path = ROOT / "scripts" / "run-alembic-from-secrets.py"
    spec = importlib.util.spec_from_file_location("run_alembic_from_secrets", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_is_tls_authenticated_and_digest_pinned() -> None:
    registry = _yaml("infra/registry/docker-compose.registry.yml")["services"]["registry"]

    assert registry["image"] == (
        "registry:3.1.1@sha256:1be55279f18a2fe1a74edf2664cac61c1bea305b7b4642dab412e7affdcb3e33"
    )
    assert registry["ports"] == ["192.168.100.100:5000:5000"]
    assert registry["environment"]["REGISTRY_AUTH"] == "htpasswd"
    assert registry["environment"]["REGISTRY_HTTP_TLS_CERTIFICATE"].endswith("registry-lan.crt")
    assert registry["environment"]["REGISTRY_HTTP_TLS_KEY"].endswith("registry-lan.key")
    assert registry["healthcheck"]["test"][0] == "CMD-SHELL"


def test_stack_requires_every_image_and_versioned_tls_secret() -> None:
    text = (ROOT / "docker-stack.yml").read_text(encoding="utf-8")

    for variable in IMAGE_VARIABLES:
        assert f"${{{variable}:?" in text
    assert "name: ${LAN_TLS_CERT_SECRET:?" in text
    assert "name: ${LAN_TLS_KEY_SECRET:?" in text


def test_bootstrap_runs_only_database_redis_and_migration() -> None:
    bootstrap = _yaml("docker-stack.bootstrap.yml")

    assert set(bootstrap["services"]) == {"db", "redis", "migrate"}
    migrate = bootstrap["services"]["migrate"]
    assert "run-alembic-from-secrets.py" in " ".join(migrate["command"])
    assert migrate["deploy"]["restart_policy"]["condition"] == "none"
    assert bootstrap["volumes"]["pgdata"] == {"external": True, "name": "growen_pgdata"}
    assert "ports" not in bootstrap["services"]["db"]


def test_single_node_override_has_no_replicas_above_one() -> None:
    override = _yaml("docker-stack.single-node.yml")

    assert override["services"]
    assert all(service["deploy"]["replicas"] == 1 for service in override["services"].values())


def test_catalog_auditor_isolated_worker_is_declared_for_swarm() -> None:
    stack = _yaml("docker-stack.yml")
    service = stack["services"]["catalog_audit_worker"]

    assert service["image"] == "${GROWEN_DRAMATIQ_IMAGE}"
    assert service["command"][-4:] == ["--threads", "1", "--queues", "catalog_audit"]
    assert service["environment"]["CATALOG_AUDIT_HEARTBEAT_ENABLED"] == "1"
    assert service["environment"]["CATALOG_AUDIT_OLLAMA_URL"] == "http://host.docker.internal:11434"
    assert service["secrets"] == ["postgres_password"]

    enrichment = stack["services"]["enrichment_worker"]
    assert enrichment["environment"]["OPENAI_API_KEY_FILE"] == "/run/secrets/openai_api_key"
    assert "openai_api_key" in enrichment["secrets"]
    assert stack["secrets"]["openai_api_key"] == {"external": True}


def test_alembic_runner_keeps_password_out_of_arguments(tmp_path, monkeypatch) -> None:
    module = _load_alembic_runner()
    password_file = tmp_path / "postgres_password"
    password_file.write_text("p@ss word", encoding="utf-8")
    captured: dict = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.run_upgrade(
        {
            "DB_HOST": "db",
            "DB_PORT": "5432",
            "DB_USER": "growen",
            "DB_NAME": "growen",
            "DB_PASS_FILE": str(password_file),
            "DB_WAIT_TIMEOUT_SECONDS": "0",
        }
    )

    assert result == 0
    assert "p@ss word" not in " ".join(captured["args"])
    assert captured["env"]["DB_URL"].startswith("postgresql+psycopg://growen:")
    assert "p%40ss%20word" in captured["env"]["DB_URL"]


def test_rollout_scripts_offer_non_mutating_previews() -> None:
    pki = (ROOT / "scripts" / "provision-lan-pki.ps1").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build-scan-push.ps1").read_text(encoding="utf-8")
    migrations = (ROOT / "scripts" / "test-postgres-migrations.ps1").read_text(encoding="utf-8")
    deploy = (ROOT / "scripts" / "deploy-swarm.ps1").read_text(encoding="utf-8")

    assert "SupportsShouldProcess" in pki and "RootKeyPasswordFile" in pki
    assert "aquasec/trivy:0.74.0@sha256:62b1e65e" in build
    assert "RegistryPasswordFile" in build and "--password-stdin" in build
    assert "Resolve-PublishedDigest" in build
    assert "docker buildx imagetools inspect" in build
    assert "registry_image_digest_invalid" in build
    assert "{{index .RepoDigests 0}}" not in build
    assert "filesystem.vulnerabilities.json" in build
    assert "MIGRATION_TEST_POSTGRES_URL" in migrations and "finally" in migrations
    assert 'ValidateSet("Preflight", "Bootstrap", "Migration", "Application")' in deploy
    assert 'ValidateSet("SingleNode", "HA")' in deploy
    assert "versioned_tls_secret_required" in deploy
    assert '--filter "status=ready"' not in deploy
    assert 'swarm_migration_ok' in deploy
    assert 'Reset-TerminalMigrationService' in deploy
    assert 'alembic_migration_already_active' in deploy
    assert '"openai_api_key"' in deploy


def test_single_node_override_avoids_start_first_deadlock() -> None:
    override = (ROOT / "docker-stack.single-node.yml").read_text(encoding="utf-8")

    for service in (
        "api",
        "frontend",
        "meli_webhook_gateway",
        "meli_sync_worker",
        "meli_cloudflared",
    ):
        assert f"{service}: {{deploy: {{replicas: 1, update_config: {{order: stop-first}}}}}}" in override


def test_postgres_migration_script_uses_windows_powershell_compatible_rng() -> None:
    migrations = (ROOT / "scripts" / "test-postgres-migrations.ps1").read_text(
        encoding="utf-8"
    )

    assert "RandomNumberGenerator]::Fill" not in migrations
    assert "$rng = [Security.Cryptography.RandomNumberGenerator]::Create()" in migrations
    assert "$rng.GetBytes($passwordBytes)" in migrations
    assert "$rng.Dispose()" in migrations


def test_pki_script_generates_distinct_certificates_with_ip_san(tmp_path) -> None:
    output = tmp_path / "pki"
    password_file = tmp_path / "root-password"
    password_file.write_text("frase-local-de-prueba-123456", encoding="utf-8")

    import pytest
    pwsh = shutil.which("pwsh.exe") or shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 (pwsh) no está disponible en este entorno")
    completed = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-File",
            str(ROOT / "scripts" / "provision-lan-pki.ps1"),
            "-IPAddress",
            "192.168.100.100",
            "-OutputDir",
            str(output),
            "-RootKeyPasswordFile",
            str(password_file),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    web = x509.load_pem_x509_certificate((output / "growen-lan.crt").read_bytes())
    registry = x509.load_pem_x509_certificate((output / "registry-lan.crt").read_bytes())
    assert web.fingerprint(web.signature_hash_algorithm) != registry.fingerprint(registry.signature_hash_algorithm)
    assert ipaddress.ip_address("192.168.100.100") in web.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value.get_values_for_type(x509.IPAddress)
    root = x509.load_pem_x509_certificate((output / "growen-lan-root-ca.crt").read_bytes())
    root_ski = root.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    web_aki = web.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
    registry_aki = registry.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
    assert web_aki == root_ski
    assert registry_aki == root_ski
    serialization.load_pem_private_key(
        (output / "growen-lan-root-ca.key").read_bytes(),
        password=b"frase-local-de-prueba-123456",
    )
