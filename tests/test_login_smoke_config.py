#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_login_smoke_config.py
# NG-HEADER: Ubicación: tests/test_login_smoke_config.py
# NG-HEADER: Descripción: Valida la carga segura de credenciales y CA del smoke LAN.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Contratos de configuración del smoke autenticado."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_smoke():
    path = ROOT / "scripts" / "test_login_flow.py"
    spec = importlib.util.spec_from_file_location("test_login_flow_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_reads_credentials_from_files(tmp_path, monkeypatch) -> None:
    module = _load_smoke()
    user_file = tmp_path / "user"
    password_file = tmp_path / "password"
    user_file.write_text("admin-lan\n", encoding="utf-8")
    password_file.write_text("clave-secreta\n", encoding="utf-8")
    monkeypatch.setenv("ADMIN_USER_FILE", str(user_file))
    monkeypatch.setenv("ADMIN_PASS_FILE", str(password_file))

    assert module._read_credential("ADMIN_USER") == "admin-lan"
    assert module._read_credential("ADMIN_PASS") == "clave-secreta"


def test_smoke_rejects_direct_credentials_by_default(monkeypatch) -> None:
    module = _load_smoke()
    monkeypatch.delenv("ADMIN_USER_FILE", raising=False)
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.delenv("SMOKE_ALLOW_DIRECT_CREDENTIALS", raising=False)

    with pytest.raises(RuntimeError, match="ADMIN_USER_FILE"):
        module._read_credential("ADMIN_USER")


def test_smoke_session_uses_explicit_ca_bundle(tmp_path, monkeypatch) -> None:
    module = _load_smoke()
    ca_bundle = tmp_path / "growen-ca.crt"
    ca_bundle.write_text("certificado", encoding="utf-8")
    monkeypatch.setenv("SMOKE_CA_BUNDLE", str(ca_bundle))

    session = module._build_session("https://192.168.100.100")

    assert session.verify == str(ca_bundle.resolve())
    assert session.headers["Origin"] == "https://192.168.100.100"


def test_smoke_uses_the_real_session_cookie_name() -> None:
    source = (ROOT / "scripts" / "test_login_flow.py").read_text(encoding="utf-8")

    assert 'cookies.get("growen_session")' in source
    assert 'cookies.get("session_id")' not in source
