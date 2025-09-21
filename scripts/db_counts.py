#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: db_counts.py
# NG-HEADER: Ubicación: scripts/db_counts.py
# NG-HEADER: Descripción: Reporte rápido de cantidades por tabla principal (users, products, suppliers, purchases).
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env", override=True)
DB_URL = os.getenv("DB_URL")
print("DB_URL:", DB_URL.replace(DB_URL.split(":")[2].split("@")[0], "***") if DB_URL else None)

engine = create_engine(DB_URL, future=True)
with engine.connect() as conn:
    def count(table: str) -> int:
        try:
            return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
        except Exception as e:
            print(f"[WARN] No se pudo contar {table}: {e}")
            return -1

    users = count("users")
    products = count("products")
    suppliers = count("suppliers")
    purchases = count("purchases")

    print({
        "users": users,
        "products": products,
        "suppliers": suppliers,
        "purchases": purchases,
    })
