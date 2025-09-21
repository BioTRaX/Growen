# NG-HEADER: Nombre de archivo: test_pop_email_import.py
# NG-HEADER: Ubicación: tests/test_pop_email_import.py
# NG-HEADER: Descripción: Tests del endpoint /purchases/import/pop-email (EML y HTML/TEXT) y SKU sintético
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402


client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _create_supplier_pop() -> int:
    r = client.post("/suppliers", json={"slug": "pop", "name": "POP"})
    assert r.status_code in (200, 201)
    # devolver el primero (en memoria suele quedar primero)
    return client.get("/suppliers").json()[0]["id"]


def test_import_pop_html_basic():
    supplier_id = _create_supplier_pop()
    html = """
    <html><body>
      <h1>Pedido 488344 Completado</h1>
      <table>
        <tr><th>Producto</th><th>Cantidad</th><th>Precio</th></tr>
        <tr><td>Maceta 12cm Negra</td><td>2</td><td>$1.500,00</td></tr>
        <tr><td>Sustrato 5L</td><td>1</td><td>$2.000,00</td></tr>
      </table>
    </body></html>
    """
    r = client.post(f"/purchases/import/pop-email?supplier_id={supplier_id}&kind=html", json={"text": html})
    assert r.status_code == 200
    pid = r.json()["purchase_id"]
    # Verificar que la compra existe y tiene líneas con SKU sintético
    g = client.get(f"/purchases/{pid}")
    assert g.status_code == 200
    data = g.json()
    assert data["status"] == "BORRADOR"
    assert len(data["lines"]) >= 2
    assert all((ln.get("supplier_sku") or "").startswith("POP-") for ln in data["lines"])  # SKU sintético


def test_import_pop_text_minimal():
    supplier_id = _create_supplier_pop()
    body = """
    Pedido 999999
    - Maceta 18cm Blanca x 3 $3000
    - Bomba de riego x 1 $12000
    """
    r = client.post(f"/purchases/import/pop-email?supplier_id={supplier_id}&kind=text", json={"text": body})
    assert r.status_code == 200
    pid = r.json()["purchase_id"]
    g = client.get(f"/purchases/{pid}")
    data = g.json()
    assert data["status"] == "BORRADOR"
    assert len(data["lines"]) >= 2
    assert all((ln.get("supplier_sku") or "").startswith("POP-") for ln in data["lines"])  # SKU sintético
