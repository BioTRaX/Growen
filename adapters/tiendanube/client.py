# NG-HEADER: Nombre de archivo: client.py
# NG-HEADER: Ubicación: adapters/tiendanube/client.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Cliente simulado de Tiendanube para pruebas."""
from typing import Any, Dict, List


class TiendaNubeClient:
    """Implementación mínima que devuelve datos de ejemplo."""

    def list_products(self) -> List[Dict[str, Any]]:
        return [{"id": 1, "title": "Producto demo"}]

    def update_inventory(self, sku: str, qty: int) -> bool:
        return True
