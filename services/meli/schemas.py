#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: schemas.py
# NG-HEADER: Ubicación: services/meli/schemas.py
# NG-HEADER: Descripción: Contratos de entrada y salida de Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Esquemas estrictos para datos externos no confiables."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MeliNotificationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    notification_id: str = Field(alias="_id", min_length=1, max_length=128)
    resource: str = Field(min_length=2, max_length=1000)
    user_id: int = Field(gt=0)
    topic: str = Field(min_length=1, max_length=64)
    application_id: int | str
    attempts: int = Field(default=0, ge=0)
    sent: datetime | None = None


class ItemLinkCreate(BaseModel):
    account_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    item_id: str = Field(pattern=r"^[A-Z]{2,4}[0-9]+$", max_length=64)
    variation_id: int | None = Field(default=None, gt=0)
