#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: normalize_skus.py
# NG-HEADER: Ubicación: scripts/normalize_skus.py
# NG-HEADER: Descripción: Script para normalizar y generar canonical_sku para productos legacy.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Normaliza canonical_sku para productos que aún no lo tienen.

Uso:
  python scripts/normalize_skus.py --dry-run
  python scripts/normalize_skus.py --apply

Estrategia:
  - Selecciona products con canonical_sku IS NULL.
  - Deriva prefijo con normalize_prefix(title).
  - Para cada prefijo mantiene un contador incremental (BEGIN desde 1).
  - Genera sufijo base con iter_candidate_suffixes(title) y toma el primero libre.
  - Construye XXX_####_YYY y verifica que no exista ya en products.canonical_sku.
  - En --dry-run solo imprime plan. En --apply ejecuta updates en batch (commit cada N).

Idempotencia: correr varias veces omite los ya actualizados.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from typing import Dict, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import engine
from db.models import Product
from db.sku_utils import normalize_prefix, build_canonical_sku, iter_candidate_suffixes, is_canonical_sku

BATCH_SIZE = 200


def load_existing(session: Session) -> Set[str]:
    rows = session.execute(select(Product.canonical_sku).where(Product.canonical_sku.is_not(None))).fetchall()
    return {r[0] for r in rows if r[0]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Normalizar canonical_sku")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Limitar cantidad de productos a procesar (0 = todos)")
    args = parser.parse_args(argv)

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"[normalize_skus] Modo: {mode}")

    with Session(engine) as session:
        existing = load_existing(session)
        print(f"Canonical SKUs existentes: {len(existing)}")

        # Candidatos (legacy con NULL)
        q = select(Product.id, Product.title, Product.sku_root).where(Product.canonical_sku.is_(None))
        if args.limit > 0:
            q = q.limit(args.limit)
        rows = session.execute(q).fetchall()
        if not rows:
            print("No hay productos pendientes de normalizar.")
            return 0
        print(f"Productos legacy a procesar: {len(rows)}")

        # Counters por prefijo
        prefix_counters: Dict[str, int] = defaultdict(int)
        planned = []

        for pid, title, sku_root in rows:
            prefix = normalize_prefix(title)
            prefix_counters[prefix] += 1
            number = prefix_counters[prefix]
            base_for_suffix = title or sku_root or "GEN"
            # Buscar sufijo libre
            chosen = None
            for candidate_suffix in iter_candidate_suffixes(base_for_suffix):
                cand = build_canonical_sku(prefix, number, candidate_suffix)
                if cand in existing:
                    continue
                chosen = cand
                break
            if not chosen:
                print(f"[WARN] No se pudo generar SKU para producto {pid}")
                continue
            existing.add(chosen)
            planned.append((pid, chosen, title))

        print(f"Plan generará {len(planned)} SKUs nuevos.")
        for pid, sku, title in planned[:20]:
            print(f"  {pid} -> {sku}  ({title[:50] if title else ''})")
        if len(planned) > 20:
            print(f"  ... {len(planned)-20} más")

        if not args.apply:
            print("Dry-run finalizado. Use --apply para persistir.")
            return 0

        # Aplicar en batches
        updated = 0
        for i in range(0, len(planned), BATCH_SIZE):
            chunk = planned[i:i+BATCH_SIZE]
            for pid, sku, _ in chunk:
                # Validación de seguridad
                if not is_canonical_sku(sku):
                    print(f"[ERROR] SKU generado inválido: {sku}")
                    continue
                session.query(Product).filter(Product.id == pid).update({Product.canonical_sku: sku})
            session.commit()
            updated += len(chunk)
            print(f"Commit batch: +{len(chunk)} (total {updated})")

        print(f"Normalización completada. Productos actualizados: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
