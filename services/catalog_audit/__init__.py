#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: __init__.py
# NG-HEADER: Ubicación: services/catalog_audit/__init__.py
# NG-HEADER: Descripción: Contratos públicos del auditor autónomo de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Auditor autónomo del catálogo de productos."""

from .fingerprint import build_input_hash
from .rules import ProductClass, QualityAuditResult, audit_catalog_content

__all__ = ["ProductClass", "QualityAuditResult", "audit_catalog_content", "build_input_hash"]
