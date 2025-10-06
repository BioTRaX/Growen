#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: diagnose_products_visibility.py
# NG-HEADER: Ubicación: scripts/diagnose_products_visibility.py
# NG-HEADER: Descripción: Diagnóstico de visibilidad de productos (counts, nulidad, huérfanos, muestras, meta).
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Diagnóstico integral para investigar por qué no se ven productos en la UI.

Métricas generadas:
  - Counts básicos (products, canonical_products, supplier_products, product_equivalences, variants, images)
  - Porcentaje de NULL en campos críticos
  - Huérfanos relacionales (supplier→product, equivalence→canonical, variants→product)
  - Muestras (primeros 5 registros de tablas clave)
  - Actividad (stock>0, status no nulo)
  - search_path, versión de Alembic, fingerprint de products

Salida: texto humano por defecto o JSON con --json. Con --verbose imprime errores SQL.

Uso:
  python scripts/diagnose_products_visibility.py
  python scripts/diagnose_products_visibility.py --json --verbose
  python scripts/diagnose_products_visibility.py --url postgresql+psycopg://growen:PASS@127.0.0.1:5433/growen --json
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import create_engine, text

try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


COUNT_QUERIES = [
    ("products", "SELECT COUNT(*) FROM products"),
    ("canonical_products", "SELECT COUNT(*) FROM canonical_products"),
    ("supplier_products", "SELECT COUNT(*) FROM supplier_products"),
    ("product_equivalences", "SELECT COUNT(*) FROM product_equivalences"),
    ("variants", "SELECT COUNT(*) FROM variants"),
    ("images", "SELECT COUNT(*) FROM images"),
]

NULL_FIELDS = [
    ("products", "status"),
    ("products", "canonical_sku"),
    ("canonical_products", "ng_sku"),
    ("supplier_products", "internal_product_id"),
    ("product_equivalences", "canonical_product_id"),
]

ORPHANS = [
    ("supplier_products_without_product", "SELECT COUNT(*) FROM supplier_products sp LEFT JOIN products p ON p.id=sp.internal_product_id WHERE sp.internal_product_id IS NOT NULL AND p.id IS NULL"),
    ("equivalences_without_canonical", "SELECT COUNT(*) FROM product_equivalences e LEFT JOIN canonical_products c ON c.id=e.canonical_product_id WHERE c.id IS NULL"),
    ("variants_without_product", "SELECT COUNT(*) FROM variants v LEFT JOIN products p ON p.id=v.product_id WHERE p.id IS NULL"),
]

SAMPLES = [
    ("products", "SELECT id, sku_root, canonical_sku, status, stock, created_at FROM products ORDER BY id LIMIT 5"),
    ("canonical_products", "SELECT id, ng_sku, sku_custom, name, sale_price, created_at FROM canonical_products ORDER BY id LIMIT 5"),
    ("supplier_products", "SELECT id, supplier_id, supplier_product_id, internal_product_id, current_purchase_price, current_sale_price FROM supplier_products ORDER BY id LIMIT 5"),
    ("product_equivalences", "SELECT id, supplier_id, supplier_product_id, canonical_product_id, confidence, source FROM product_equivalences ORDER BY id LIMIT 5"),
]

EXTRA_ACTIVITY = [
    ("products_with_stock", "SELECT COUNT(*) FROM products WHERE stock > 0"),
    ("products_with_status", "SELECT COUNT(*) FROM products WHERE status IS NOT NULL"),
]

META_QUERIES = [
    ("search_path", "SHOW search_path"),
    ("alembic_version", "SELECT version_num FROM alembic_version"),
    ("products_fingerprint", "SELECT md5(string_agg(id::text || ':' || COALESCE(sku_root,'') || ':' || COALESCE(canonical_sku,''), ',' ORDER BY id)) FROM products"),
]


@dataclass
class CountInfo:
    table: str
    count: int


@dataclass
class NullStat:
    table: str
    field: str
    nulls: int
    total: int
    pct: float


@dataclass
class OrphanStat:
    name: str
    count: int


@dataclass
class SampleTable:
    table: str
    rows: List[Dict[str, Any]]


@dataclass
class Report:
    counts: List[CountInfo]
    null_stats: List[NullStat]
    orphans: List[OrphanStat]
    samples: List[SampleTable]
    meta: Dict[str, Any]


def _safe_exec(conn, sql: str, verbose: bool):
    try:
        return conn.execute(text(sql))
    except Exception as e:  # pragma: no cover
        if verbose:
            print(f"[ERROR] SQL: {sql}\n{e}\n{traceback.format_exc()}")
        return None


def build_report(url: str, verbose: bool = False) -> Report:
    engine = create_engine(url, future=True)
    counts: List[CountInfo] = []
    nulls: List[NullStat] = []
    orphans: List[OrphanStat] = []
    samples: List[SampleTable] = []
    meta: Dict[str, Any] = {}
    with engine.connect() as conn:
        # Counts
        for name, q in COUNT_QUERIES:
            res = _safe_exec(conn, q, verbose)
            val = res.scalar_one() if res else -1
            counts.append(CountInfo(name, int(val)))
        total_map = {c.table: c.count for c in counts}
        # Null stats
        for tbl, field in NULL_FIELDS:
            total = total_map.get(tbl, 0)
            if total <= 0:
                nulls.append(NullStat(tbl, field, -1, total, 0.0))
                continue
            res = _safe_exec(conn, f"SELECT COUNT(*) FROM {tbl} WHERE {field} IS NULL", verbose)
            n = res.scalar_one() if res else -1
            pct = round((n / total) * 100, 2) if (n >= 0 and total > 0) else 0.0
            nulls.append(NullStat(tbl, field, int(n), int(total), pct))
        # Orphans
        for name, q in ORPHANS:
            res = _safe_exec(conn, q, verbose)
            o = res.scalar_one() if res else -1
            orphans.append(OrphanStat(name, int(o)))
        # Samples
        for tbl, q in SAMPLES:
            res = _safe_exec(conn, q, verbose)
            rows_list: List[Dict[str, Any]] = []
            if res:
                rows = res.mappings().all()
                rows_list = [dict(r) for r in rows]
            samples.append(SampleTable(tbl, rows_list))
        # Extra activity
        for name, q in EXTRA_ACTIVITY:
            res = _safe_exec(conn, q, verbose)
            meta[name] = int(res.scalar_one()) if res else -1
        # Meta queries
        for name, q in META_QUERIES:
            res = _safe_exec(conn, q, verbose)
            meta[name] = res.scalar_one() if res else None
    return Report(counts, nulls, orphans, samples, meta)


def _load_env():
    if "DB_URL" not in os.environ and load_dotenv:
        p = Path('.env')
        if p.exists():
            load_dotenv(p)


def parse_args():
    ap = argparse.ArgumentParser(description="Diagnóstico visibilidad productos")
    ap.add_argument("--url", help="DB URL override")
    ap.add_argument("--json", action="store_true", help="Salida JSON")
    ap.add_argument("--verbose", action="store_true", help="Logs de errores SQL")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    _load_env()
    url = args.url or os.getenv("DB_URL")
    if not url:
        print("DB_URL no definida. Use --url o exporte la variable.")
        return 2
    if args.verbose:
        print(f"[INFO] Usando DB_URL={url}")
    rep = build_report(url, verbose=args.verbose)
    if args.json:
        def _convert(obj: Any):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            return obj
        # Normalizar rows de samples
        norm_samples = []
        for s in rep.samples:
            norm_rows = []
            for row in s.rows:
                norm_rows.append({k: _convert(v) for k, v in row.items()})
            norm_samples.append({"table": s.table, "rows": norm_rows})
        payload = {
            "counts": [asdict(c) for c in rep.counts],
            "null_stats": [asdict(n) for n in rep.null_stats],
            "orphans": [asdict(o) for o in rep.orphans],
            "samples": norm_samples,
            "meta": {k: _convert(v) for k, v in rep.meta.items()},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    # Texto humano
    print("== Counts ==")
    for c in rep.counts:
        print(f"{c.table}: {c.count}")
    print("\n== Null stats ==")
    for n in rep.null_stats:
        print(f"{n.table}.{n.field}: {n.nulls}/{n.total} ({n.pct}%)")
    print("\n== Orphans ==")
    for o in rep.orphans:
        print(f"{o.name}: {o.count}")
    print("\n== Activity ==")
    for k, v in rep.meta.items():
        if k in ("products_with_stock", "products_with_status"):
            print(f"{k}: {v}")
    print("\n== Meta ==")
    for k, v in rep.meta.items():
        if k not in ("products_with_stock", "products_with_status"):
            print(f"{k}: {v}")
    print("\n== Samples ==")
    for s in rep.samples:
        print(f"[{s.table}]")
        if not s.rows:
            print("  (sin filas / error)")
        for row in s.rows:
            print("  ", row)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
