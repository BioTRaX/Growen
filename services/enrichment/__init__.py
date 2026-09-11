#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: __init__.py
# NG-HEADER: Ubicación: services/enrichment/__init__.py
# NG-HEADER: Descripción: Paquete de servicios de enriquecimiento y auditoría de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicios del dominio de enriquecimiento canónico."""

from .auditor import QualityAuditResult, audit_enrichment_proposal

__all__ = ["QualityAuditResult", "audit_enrichment_proposal"]
