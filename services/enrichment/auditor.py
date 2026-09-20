#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: auditor.py
# NG-HEADER: Ubicación: services/enrichment/auditor.py
# NG-HEADER: Descripción: Fachada temporal de compatibilidad para lecturas históricas del auditor.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Compatibilidad temporal; las reglas pertenecen a ``services.catalog_audit``."""

from services.catalog_audit.rules import (  # noqa: F401
    CRITICAL_FLAGS,
    FLAG_BOILERPLATE,
    FLAG_DIMENSIONS_MISMATCH,
    FLAG_ENTITY_MISMATCH,
    FLAG_INVALID_DIMENSIONS,
    FLAG_MALFORMED_HTML,
    FLAG_PHYSICAL_DISCREPANCY,
    FLAG_SUSPICIOUS_DIMENSIONS,
    QualityAuditResult,
    audit_enrichment_proposal,
    extract_volume_liters,
    extract_weight_kg_from_text,
)

__all__ = [
    "CRITICAL_FLAGS",
    "FLAG_BOILERPLATE",
    "FLAG_DIMENSIONS_MISMATCH",
    "FLAG_ENTITY_MISMATCH",
    "FLAG_INVALID_DIMENSIONS",
    "FLAG_MALFORMED_HTML",
    "FLAG_PHYSICAL_DISCREPANCY",
    "FLAG_SUSPICIOUS_DIMENSIONS",
    "QualityAuditResult",
    "audit_enrichment_proposal",
    "extract_volume_liters",
    "extract_weight_kg_from_text",
]
