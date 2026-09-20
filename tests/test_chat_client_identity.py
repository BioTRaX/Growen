#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_client_identity.py
# NG-HEADER: Ubicación: tests/test_chat_client_identity.py
# NG-HEADER: Descripción: Verifica identidades web seudónimas sin exponer datos del cliente.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Pruebas de la identidad estable usada por Chat HTTP y WebSocket."""

from services.auth import pseudonymous_client_id


def test_pseudonymous_client_id_is_stable_and_opaque() -> None:
    host = "192.168.100.25"
    user_agent = "Browser/123 dispositivo-personal"

    first = pseudonymous_client_id(host, user_agent, secret="secret-a")
    second = pseudonymous_client_id(host, user_agent, secret="secret-a")

    assert first == second
    assert len(first) == 32
    assert host not in first
    assert "Browser" not in first


def test_pseudonymous_client_id_is_scoped_by_secret() -> None:
    first = pseudonymous_client_id("192.168.100.25", "Browser/123", secret="secret-a")
    second = pseudonymous_client_id("192.168.100.25", "Browser/123", secret="secret-b")

    assert first != second
