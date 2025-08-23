"""Handlers de intents de ejemplo."""
from typing import Any, Dict, List



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
    """Ejecuta operaciones de stock básicas."""
    if not args:
        return {"message": "Acción requerida: adjust|min"}
    action = args[0]
    sku = opts.get("sku")
    qty = opts.get("qty")
    if action == "adjust":
        return {
            "message": f"Stock ajustado para {sku} en {qty}",
            "action": "adjust",
            "sku": sku,
            "qty": int(qty) if isinstance(qty, str) and qty.isdigit() else qty,
        }
    if action == "min":
        return {
            "message": f"Stock mínimo de {sku} en {qty}",
            "action": "min",
            "sku": sku,
            "min": int(qty) if isinstance(qty, str) and qty.isdigit() else qty,
        }
    return {"message": f"Acción desconocida: {action}"}


def handle_import(args: List[str], opts: Dict[str, Any]) -> Dict[str, Any]:
    """Simula la importación de archivos de proveedores."""
    if not args:
        return {"message": "Falta archivo a importar"}
    filename = args[0]
    supplier = opts.get("supplier")
    dry_run = bool(opts.get("dry_run") or opts.get("dry-run"))
    return {
        "message": f"Importando {filename} (supplier={supplier}, dry_run={dry_run})",
        "file": filename,
        "supplier": supplier,
        "dry_run": dry_run,
    }


def handle_search(args: List[str], opts: Dict[str, Any]) -> Dict[str, Any]:
    """Busca productos por texto o SKU."""
    query = " ".join(args) or opts.get("q", "")
    return {"message": f"Buscando '{query}'", "query": query}
