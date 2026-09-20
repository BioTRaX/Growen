#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: source_validation.py
# NG-HEADER: Ubicación: services/market/source_validation.py
# NG-HEADER: Descripción: Validación segura y focal de URLs de fuentes de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Controles SSRF y estado inicial de fuentes externas de Mercado."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceValidation:
    status: str
    ars_confirmed: bool | None
    argentina_delivery_confirmed: bool | None
    detail: dict[str, object]


def _public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return not any((address.is_private, address.is_loopback, address.is_link_local, address.is_reserved, address.is_multicast))


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("La URL debe usar HTTP o HTTPS y contener un dominio")
    if parsed.username or parsed.password:
        raise ValueError("La URL no puede contener credenciales")
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal = None
    if literal and not _public_address(str(literal)):
        raise ValueError("La URL apunta a una red no pública")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError("No se pudo resolver el dominio de la fuente") from exc
    if not addresses or any(not _public_address(address) for address in addresses):
        raise ValueError("El dominio resuelve a una red no pública")


def initial_validation(*, currency: str, manual: bool, attested_argentina_delivery: bool = False) -> SourceValidation:
    if currency.upper() != "ARS":
        return SourceValidation("rejected", False, None, {"reason": "currency_not_ars"})
    if manual:
        return SourceValidation(
            "warning",
            True,
            True if attested_argentina_delivery else None,
            {"reason": "manual_attestation", "delivery_attested": attested_argentina_delivery},
        )
    return SourceValidation("warning", True, None, {"reason": "automatic_validation_pending"})
