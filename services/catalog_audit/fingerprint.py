#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: fingerprint.py
# NG-HEADER: Ubicación: services/catalog_audit/fingerprint.py
# NG-HEADER: Descripción: Huella estable de contenido, reglas y feedback aplicable.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Construcción determinista de identidades de auditoría."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        text = unicodedata.normalize("NFKC", value).strip().lower()
        return re.sub(r"\s+", " ", text)
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))}
    if isinstance(value, (list, tuple, set)):
        normalized = [_normalize(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False, default=str))
    return value


def build_input_hash(
    *,
    name: str,
    brand: str | None,
    taxonomy: dict[str, Any] | None,
    content: dict[str, Any],
    rules_version: str,
    feedback_version: str,
) -> str:
    payload = _normalize({
        "name": name,
        "brand": brand,
        "taxonomy": taxonomy or {},
        "content": content,
        "rules_version": rules_version,
        "feedback_version": feedback_version,
    })
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
