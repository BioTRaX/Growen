# NG-HEADER: Nombre de archivo: handlers.py
# NG-HEADER: Ubicación: services/intents/handlers.py
# NG-HEADER: Descripción: Handlers que resuelven intents soportados.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Handlers de intents de ejemplo."""

from typing import Any, Dict, List, Callable
import asyncio
import threading
from sqlalchemy import select

from db.session import SessionLocal
def _run_blocking(coro_func: Callable[[], Any]):
    """Ejecuta una corrutina en un hilo separado para evitar RuntimeError
    cuando ya existe un event loop en ejecución (pytest-asyncio).

    Retorna el resultado de la corrutina, propagando excepciones.
    """
    result: dict = {}
    err: dict = {}

    def _target():
        try:
            res = asyncio.run(coro_func())
            result["value"] = res
        except BaseException as e:  # propaga cualquier excepción
            err["exc"] = e

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()
    if "exc" in err:
        raise err["exc"]
    return result.get("value")
from db.models import Variant, Inventory, Supplier
from services.routers.catalog import update_product_stock, StockUpdate
from services.routers import catalog as catalog_router
from services.routers import imports as imports_router
from services.suppliers.parsers import SUPPLIER_PARSERS


def handle_help(args: List[str], opts: Dict[str, Any]) -> Dict[str, str]:
    """Devuelve texto de ayuda simple."""
    return {
        "message": (
            "Comandos disponibles: /help, /sync pull, /sync push, "
            "/stock adjust, /stock min, /import <archivo> --supplier=SLUG, "
            "/search <texto>"
        )
    }


def handle_stock(args: List[str], opts: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta operaciones de stock contra el catálogo."""
    if not args:
        return {"message": "Acción requerida: adjust|min"}
    action = args[0]
    sku = opts.get("sku")
    qty_raw = opts.get("qty")
    qty = int(qty_raw) if qty_raw is not None else None
    if not sku or qty is None:
        return {"message": "sku y qty requeridos"}

    if action == "adjust":
        async def _adjust() -> Dict[str, Any] | None:
            async with SessionLocal() as session:
                var = await session.scalar(select(Variant).where(Variant.sku == sku))
                if not var:
                    return None
                inv = await session.scalar(
                    select(Inventory).where(Inventory.variant_id == var.id)
                )
                if not inv:
                    inv = Inventory(variant_id=var.id, stock_qty=qty)
                    session.add(inv)
                else:
                    inv.stock_qty = qty
                await update_product_stock(
                    var.product_id, StockUpdate(stock=qty), session=session
                )
                await session.commit()
                return {
                    "action": "adjust",
                    "sku": sku,
                    "qty": qty,
                    "product_id": var.product_id,
                }

        res = _run_blocking(_adjust)
        if not res:
            return {"message": f"SKU no encontrado: {sku}"}
        res["message"] = f"Stock ajustado para {sku} en {qty}"
        return res

    if action == "min":
        async def _min() -> Dict[str, Any] | None:
            async with SessionLocal() as session:
                var = await session.scalar(select(Variant).where(Variant.sku == sku))
                if not var:
                    return None
                inv = await session.scalar(
                    select(Inventory).where(Inventory.variant_id == var.id)
                )
                if not inv:
                    inv = Inventory(variant_id=var.id, stock_qty=0, min_qty=qty)
                    session.add(inv)
                else:
                    inv.min_qty = qty
                await session.commit()
                return {
                    "action": "min",
                    "sku": sku,
                    "min": qty,
                }

        res = _run_blocking(_min)
        if not res:
            return {"message": f"SKU no encontrado: {sku}"}
        res["message"] = f"Stock mínimo de {sku} en {qty}"
        return res

    return {"message": f"Acción desconocida: {action}"}


def handle_import(args: List[str], opts: Dict[str, Any]) -> Dict[str, Any]:
    """Importa archivos de proveedores usando los parsers disponibles."""
    if not args:
        return {"message": "Falta archivo a importar"}
    filename = args[0]
    supplier_slug = opts.get("supplier")
    dry_run = bool(opts.get("dry_run") or opts.get("dry-run"))
    if not supplier_slug:
        return {"message": "Proveedor requerido"}

    parser = SUPPLIER_PARSERS.get(supplier_slug)
    if not parser:
        return {"message": f"Parser no encontrado para {supplier_slug}"}
    with open(filename, "rb") as fh:
        rows = parser.parse_bytes(fh.read())

    if dry_run:
        ok_rows = sum(1 for r in rows if r.get("status") == "ok")
        return {
            "message": f"{ok_rows} filas procesadas (dry_run)",
            "rows": ok_rows,
            "dry_run": True,
            "file": filename,
            "supplier": supplier_slug,
        }

    async def _apply() -> Dict[str, Any]:
        async with SessionLocal() as session:
            supplier = await session.scalar(
                select(Supplier).where(Supplier.slug == supplier_slug)
            )
            if not supplier:
                return {"error": f"Proveedor {supplier_slug} no encontrado"}
            imported = 0
            for row in rows:
                if row.get("status") != "ok":
                    continue
                cat = await imports_router._get_or_create_category_path(
                    session, row.get("categoria_path", "")
                )
                prod = await imports_router._upsert_product(
                    session, row["codigo"], row["nombre"], cat
                )
                await imports_router._upsert_supplier_product(
                    session, supplier.id, row, prod
                )
                imported += 1
            await session.commit()
            return {"imported": imported}

    result = _run_blocking(_apply)
    if "error" in result:
        return {"message": result["error"]}
    return {
        "message": f"Importadas {result['imported']} filas",
        "imported": result["imported"],
        "file": filename,
        "supplier": supplier_slug,
        "dry_run": False,
    }


def handle_search(args: List[str], opts: Dict[str, Any]) -> Dict[str, Any]:
    """Busca productos utilizando el catálogo."""
    query = " ".join(args) or opts.get("q", "")
    if not query:
        return {"message": "Texto de búsqueda requerido", "items": []}

    async def _search() -> Dict[str, Any]:
        async with SessionLocal() as session:
            return await catalog_router.list_products(q=query, session=session)

    data = _run_blocking(_search)
    return {
        "message": f"{data['total']} resultados para '{query}'",
        "items": data["items"],
        "query": query,
    }
