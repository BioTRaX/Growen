#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: ai_models.py
# NG-HEADER: Ubicación: services/importers/ai_models.py
# NG-HEADER: Descripción: Modelos Pydantic para respuesta AI fallback remitos
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Modelos Pydantic relacionados a la etapa de fallback con IA para remitos.

Se mantiene separado de la lógica de cliente para facilitar pruebas unitarias
sin requerir llamadas externas. La salida esperada de la IA es estrictamente
JSON y debe validarse contra estos modelos antes de usarse en la pipeline.
"""
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


AllowedUnit = Literal["UN", "KG", "GR", "LT", "ML", "PACK", "CJ"]


class RemitoAIItem(BaseModel):
    supplier_sku: Optional[str] = Field(None, description="SKU del proveedor si se detecta (3-12 chars alfanum).")
    title: str = Field(..., min_length=2, max_length=400)
    qty: Decimal = Field(..., ge=0)
    unit_cost_bonif: Decimal = Field(..., ge=0, description="Precio unitario con bonificación ya aplicada si corresponde")
    pct_bonif: Decimal = Field(0, ge=0, le=100)
    unit: Optional[AllowedUnit] = Field(None, description="Unidad normalizada opcional")
    confidence: float = Field(..., ge=0, le=1, description="Confianza de la IA sobre esta línea")

    @field_validator("supplier_sku")
    @classmethod
    def _norm_sku(cls, v: Optional[str]):
        if not v:
            return v
        v2 = v.strip().upper()
        # permitir dígitos y letras sin espacios, truncar largo excesivo
        v2 = "".join(ch for ch in v2 if ch.isalnum())[:20]
        return v2 or None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str):
        return " ".join(v.split())


class RemitoAIPayload(BaseModel):
    remito_number: Optional[str] = Field(None, max_length=32)
    remito_date: Optional[str] = Field(None, description="Fecha ISO YYYY-MM-DD si se detecta")
    lines: List[RemitoAIItem] = Field(default_factory=list)
    model: Optional[str] = None
    total_lines: int = Field(0, ge=0)
    overall_confidence: float = Field(0, ge=0, le=1)

    @field_validator("lines")
    @classmethod
    def _set_total(cls, v):
        return v

    def compute_overall(self) -> float:
        if not self.lines:
            self.overall_confidence = 0
        else:
            self.overall_confidence = float(sum(l.confidence for l in self.lines) / len(self.lines))
        self.total_lines = len(self.lines)
        return self.overall_confidence


__all__ = [
    "RemitoAIItem",
    "RemitoAIPayload",
    "AllowedUnit",
]
