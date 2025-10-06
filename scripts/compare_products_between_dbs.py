#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: compare_products_between_dbs.py
# NG-HEADER: Ubicación: scripts/compare_products_between_dbs.py
# NG-HEADER: Descripción: Comparación entre dos bases (counts, nulls, fingerprints, diffs IDs) para productos y tablas relacionadas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Herramienta para comparar estado de datos entre dos bases Postgres.

Enfoque actual:
  - Tablas clave: products, canonical_products, supplier_products, product_equivalences, variants, images
  - Métricas: counts, null ratios en campos críticos, fingerprint md5 de products, rangos de IDs, sets de IDs (diferencias), versión alembic, search_path.
  - Heurística de calidad simple (source es 'mejor' si tiene >= counts y menor % de nulls).

Uso:
  python scripts/compare_products_between_dbs.py \
    --source-url postgresql+psycopg://growen:PASS@127.0.0.1:5433/growen_old \
    --target-url postgresql+psycopg://growen:PASS@127.0.0.1:5433/growen \
    --json --verbose

Requisitos:
  - SQLAlchemy + psycopg
  - Opcional: python-dotenv para cargar .env si no se pasan URLs.

Limitaciones:
  - No compara contenido semántico (nombres, precios) salvo fingerprint concatenado.
  - No detecta divergencias de esquema (se podría extender consultando information_schema.columns).

Extensiones futuras sugeridas:
  - Diferencias campo a campo (muestras) cuando fingerprints difieren.
  - Exportación CSV de IDs faltantes.
  - Comparación de updated_at / created_at para frescura.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import traceback
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Tuple
from pathlib import Path
from sqlalchemy import create_engine, text

try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

TABLES = [
    "products",
    "canonical_products",
    "supplier_products",
    "product_equivalences",
    "variants",
    "images",
]

NULL_FIELDS = [
    ("products", "canonical_sku"),
    ("products", "status"),
    ("canonical_products", "ng_sku"),
    ("supplier_products", "internal_product_id"),
]

FINGERPRINT_SQL = "SELECT md5(string_agg(id::text || ':' || COALESCE(CASE WHEN pg_catalog.pg_attribute.attisdropped IS NOT TRUE THEN sku_root END,'') || ':' || COALESCE(CASE WHEN pg_catalog.pg_attribute.attisdropped IS NOT TRUE THEN canonical_sku END,''), ',' ORDER BY id)) FROM products"  # se reescribe dinámicamente si faltan columnas

META_QUERIES = [
    ("alembic_version", "SELECT version_num FROM alembic_version"),
    ("search_path", "SHOW search_path"),
]

@dataclass
class TableStats:
    table: str
    count: int
    id_min: int | None
    id_max: int | None

@dataclass
class NullRatio:
    table: str
    field: str
    nulls: int
    total: int
    pct: float

@dataclass
class DBProfile:
    url: str
    meta: Dict[str, Any]
    tables: List[TableStats]
    nulls: List[NullRatio]
    products_fingerprint: str | None
    products_only_in_this: List[int]
    products_missing_here: List[int]

@dataclass
class ComparisonResult:
    source: DBProfile
    target: DBProfile
    heuristic_preference: str | None  # 'source' | 'target' | None
    notes: List[str]


def _load_env():
    if load_dotenv and not os.getenv("DB_URL"):
        env = Path('.env')
        if env.exists():
            load_dotenv(env)

def _safe_exec(conn, sql: str, verbose: bool):
    try:
        return conn.execute(text(sql))
    except Exception as e:  # pragma: no cover
        if verbose:
            print(f"[ERROR] SQL: {sql}\n{e}\n{traceback.format_exc()}")
        return None


def profile_db(url: str, verbose: bool = False, limit_id_diff: int = 50) -> DBProfile:
    engine = create_engine(url, future=True)
    tables: List[TableStats] = []
    nulls: List[NullRatio] = []
    meta: Dict[str, Any] = {}
    fp: str | None = None
    # Detectar columnas existentes en products y canonical_products para evitar errores
    existing_cols_products: set[str] = set()
    existing_cols_canonical: set[str] = set()
    with engine.connect() as conn:
        col_rs = _safe_exec(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='products'", verbose)
        if col_rs:
            existing_cols_products = {r[0] for r in col_rs.fetchall()}
        col_rs2 = _safe_exec(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='canonical_products'", verbose)
        if col_rs2:
            existing_cols_canonical = {r[0] for r in col_rs2.fetchall()}
    with engine.connect() as conn:
        # meta
        for name, q in META_QUERIES:
            r = _safe_exec(conn, q, verbose)
            meta[name] = r.scalar_one() if r else None
        # tables
        for t in TABLES:
            q = _safe_exec(conn, f"SELECT COUNT(*), MIN(id), MAX(id) FROM {t}", verbose)
            if q:
                c, mn, mx = q.fetchone()
                tables.append(TableStats(t, int(c), mn, mx))
            else:
                tables.append(TableStats(t, -1, None, None))
        total_map = {ts.table: ts.count for ts in tables}
        # null ratios con verificación de columna
        for tbl, fld in NULL_FIELDS:
            total = total_map.get(tbl, 0)
            if total <= 0:
                nulls.append(NullRatio(tbl, fld, -1, total, 0.0))
                continue
            if tbl == 'products' and fld not in existing_cols_products:
                nulls.append(NullRatio(tbl, fld, -1, total, 0.0))
                continue
            if tbl == 'canonical_products' and fld not in existing_cols_canonical:
                nulls.append(NullRatio(tbl, fld, -1, total, 0.0))
                continue
            r = _safe_exec(conn, f"SELECT COUNT(*) FROM {tbl} WHERE {fld} IS NULL", verbose)
            n = r.scalar_one() if r else -1
            pct = round((n / total) * 100, 2) if (n >= 0 and total > 0) else 0.0
            nulls.append(NullRatio(tbl, fld, int(n), int(total), pct))
        # fingerprint products dinámico según columnas
        fp_cols = []
        if 'sku_root' in existing_cols_products:
            fp_cols.append("COALESCE(sku_root,'')")
        if 'canonical_sku' in existing_cols_products:
            fp_cols.append("COALESCE(canonical_sku,'')")
        if not fp_cols:  # fallback a solo id
            fp_expr = "id::text"
        else:
            fp_expr = "id::text || ':' || " + " || ':' || ".join(fp_cols)
        rfp = _safe_exec(conn, f"SELECT md5(string_agg({fp_expr}, ',' ORDER BY id)) FROM products", verbose)
        fp = rfp.scalar_one() if rfp else None
    return DBProfile(url=url, meta=meta, tables=tables, nulls=nulls,
                     products_fingerprint=fp, products_only_in_this=[], products_missing_here=[])


def diff_products(source: DBProfile, target: DBProfile, limit: int = 50) -> Tuple[List[int], List[int]]:
    # Para eficiencia, volvemos a consultar listas de IDs solo si faltaban.
    def fetch_ids(url: str) -> List[int]:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            r = conn.execute(text("SELECT id FROM products ORDER BY id"))
            return [row[0] for row in r.fetchall()]
    s_ids = fetch_ids(source.url)
    t_ids = fetch_ids(target.url)
    set_s = set(s_ids)
    set_t = set(t_ids)
    only_source = sorted(list(set_s - set_t))[:limit]
    only_target = sorted(list(set_t - set_s))[:limit]
    return only_source, only_target


def heuristic(source: DBProfile, target: DBProfile) -> Tuple[str | None, List[str]]:
    notes: List[str] = []
    pref: str | None = None
    # Regla 1: versión alembic
    s_ver = source.meta.get("alembic_version")
    t_ver = target.meta.get("alembic_version")
    if s_ver != t_ver:
        notes.append(f"VersionAlembic: source={s_ver} target={t_ver}")
        # Simple: si difieren y no sabemos orden lexicográfico real, no decidir solo por esto.
    # Regla 2: counts products
    s_products = next((t.count for t in source.tables if t.table == "products"), -1)
    t_products = next((t.count for t in target.tables if t.table == "products"), -1)
    if s_products > t_products:
        notes.append("source tiene más products")
    elif t_products > s_products:
        notes.append("target tiene más products")
    # Regla 3: null ratio canonical_sku menor es mejor si counts similares
    s_null_can = next((n.pct for n in source.nulls if n.table == "products" and n.field == "canonical_sku"), 0)
    t_null_can = next((n.pct for n in target.nulls if n.table == "products" and n.field == "canonical_sku"), 0)
    if s_products >= t_products and s_null_can <= t_null_can:
        pref = "source"
    elif t_products >= s_products and t_null_can <= s_null_can:
        pref = "target"
    return pref, notes


def build_comparison(source_url: str, target_url: str, verbose: bool, limit: int) -> ComparisonResult:
    source_prof = profile_db(source_url, verbose=verbose, limit_id_diff=limit)
    target_prof = profile_db(target_url, verbose=verbose, limit_id_diff=limit)
    only_source, only_target = diff_products(source_prof, target_prof, limit=limit)
    source_prof.products_only_in_this = only_source
    target_prof.products_only_in_this = only_target  # simétrico
    # Para claridad: products_missing_here = los que el otro tiene y yo no.
    source_prof.products_missing_here = only_target
    target_prof.products_missing_here = only_source
    pref, notes = heuristic(source_prof, target_prof)
    return ComparisonResult(source=source_prof, target=target_prof, heuristic_preference=pref, notes=notes)


def parse_args():
    ap = argparse.ArgumentParser(description="Comparación entre dos bases de datos (productos)")
    ap.add_argument("--source-url", help="URL base fuente (ej: growen_old)")
    ap.add_argument("--target-url", help="URL base destino / actual")
    ap.add_argument("--limit", type=int, default=50, help="Límite de IDs listados en diffs")
    ap.add_argument("--json", action="store_true", help="Salida JSON")
    ap.add_argument("--verbose", action="store_true", help="Logs de errores SQL")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    _load_env()
    src = args.source_url or os.getenv("SOURCE_DB_URL")
    tgt = args.target_url or os.getenv("TARGET_DB_URL") or os.getenv("DB_URL")
    if not src or not tgt:
        print("Debe especificar --source-url y --target-url (o variables SOURCE_DB_URL / TARGET_DB_URL).")
        return 2
    if args.verbose:
        print(f"[INFO] source={src}\n[INFO] target={tgt}")
    comp = build_comparison(src, tgt, verbose=args.verbose, limit=args.limit)
    if args.json:
        payload = {
            "source": {
                "url": comp.source.url,
                "meta": comp.source.meta,
                "tables": [asdict(t) for t in comp.source.tables],
                "nulls": [asdict(n) for n in comp.source.nulls],
                "fingerprint": comp.source.products_fingerprint,
                "products_only_in_this": comp.source.products_only_in_this,
                "products_missing_here": comp.source.products_missing_here,
            },
            "target": {
                "url": comp.target.url,
                "meta": comp.target.meta,
                "tables": [asdict(t) for t in comp.target.tables],
                "nulls": [asdict(n) for n in comp.target.nulls],
                "fingerprint": comp.target.products_fingerprint,
                "products_only_in_this": comp.target.products_only_in_this,
                "products_missing_here": comp.target.products_missing_here,
            },
            "heuristic_preference": comp.heuristic_preference,
            "notes": comp.notes,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    # Modo texto
    print("== META ==")
    print(f"Source alembic={comp.source.meta.get('alembic_version')}  Target alembic={comp.target.meta.get('alembic_version')}")
    print("\n== COUNTS ==")
    for st in comp.source.tables:
        tgt_ts = next((t for t in comp.target.tables if t.table == st.table), None)
        tcount = tgt_ts.count if tgt_ts else 'NA'
        print(f"{st.table}: source={st.count} target={tcount}")
    print("\n== NULL RATIOS (products.canonical_sku, status, etc.) ==")
    for sn in comp.source.nulls:
        tn = next((n for n in comp.target.nulls if n.table == sn.table and n.field == sn.field), None)
        tval = f"{tn.nulls}/{tn.total} ({tn.pct}%)" if tn else 'NA'
        print(f"{sn.table}.{sn.field}: source={sn.nulls}/{sn.total} ({sn.pct}%) target={tval}")
    print("\n== FINGERPRINT PRODUCTS ==")
    print(f"source={comp.source.products_fingerprint}\n target={comp.target.products_fingerprint}")
    print("\n== DIFF IDs (hasta limite) ==")
    print(f"Solo en source: {comp.source.products_only_in_this}")
    print(f"Solo en target: {comp.target.products_only_in_this}")
    print("\n== HEURISTIC ==")
    print(f"Preferencia heurística: {comp.heuristic_preference}")
    if comp.notes:
        print("Notas:")
        for n in comp.notes:
            print(f" - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
