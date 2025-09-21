#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_notion_errors.py
# NG-HEADER: Ubicación: tests/test_notion_errors.py
# NG-HEADER: Descripción: Tests de matching y fingerprint para integración de errores Notion
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import pytest

from services.integrations.notion_errors import ErrorEvent, match_known_error, fingerprint_error


def test_match_known_error_db_unique():
    ev = ErrorEvent(
        servicio="api",
        entorno="test",
        url="http://localhost/api/products",
        codigo="IntegrityError",
        mensaje="duplicate key value violates unique constraint \nDETAIL: Key (sku)=(ABC) already exists.",
        stacktrace=None,
    )
    matched = match_known_error(ev)
    assert matched is not None
    assert matched.get("id") == "db-unique-violation"


def test_fingerprint_stability_basic():
    ev1 = ErrorEvent(
        servicio="api",
        entorno="test",
        url="http://example.com/purchases?id=123&x=1",
        codigo="TimeoutError",
        mensaje="Read timed out while calling provider\nTraceback: ...",
    )
    matched1 = match_known_error(ev1)
    fp1 = fingerprint_error(ev1, matched1)

    # Cambios en querystring o en líneas posteriores del mensaje no deberían cambiar el hash
    ev2 = ErrorEvent(
        servicio="api",
        entorno="test",
        url="http://example.com/purchases?id=456&x=2",
        codigo="TimeoutError",
        mensaje="Read timed out while calling provider\notra línea que varía",
    )
    matched2 = match_known_error(ev2)
    fp2 = fingerprint_error(ev2, matched2)

    assert fp1 == fp2

    # Cambiar el código de error sí cambia el fingerprint
    ev3 = ErrorEvent(
        servicio="api",
        entorno="test",
        url="http://example.com/purchases?id=456&x=2",
        codigo="ConnectionReset",
        mensaje="Read timed out while calling provider\n...",
    )
    matched3 = match_known_error(ev3)
    fp3 = fingerprint_error(ev3, matched3)
    assert fp3 != fp1
