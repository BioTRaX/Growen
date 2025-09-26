# NG-HEADER: Nombre de archivo: test_pop_email_dollar_heuristic.py
# NG-HEADER: Ubicación: tests/test_pop_email_dollar_heuristic.py
# NG-HEADER: Descripción: Testea la heurística de conteo por "$" y fallback en parser POP
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
    return client.get("/suppliers").json()[0]["id"]


def test_pop_html_dollar_estimation_and_fallback():
    supplier_id = _create_supplier_pop()
    # HTML malformado que no arma tabla correcta, pero contiene 2 ítems + Subtotal/Total/Ahorro
    html = """
    <html><body>
      <div>Pedido 123456 Completado</div>
      <div>Maceta de cultivo 18cm - x 2 $1.500,00</div>
      <div>Sustrato Premium 5L x 1 $2.000,00</div>
      <div>Subtotal: $5.000,00</div>
      <div>Ahorro: $500,00</div>
      <div>Total: $4.500,00</div>
    </body></html>
    """
    r = client.post(f"/purchases/import/pop-email?supplier_id={supplier_id}&kind=html", json={"text": html})
    assert r.status_code == 200
    # Debe crear al menos 2 líneas (2 precios de ítems) pese a que no hubo tabla
    pid = r.json()["purchase_id"]
    g = client.get(f"/purchases/{pid}")
    assert g.status_code == 200
    data = g.json()
    assert data["status"] == "BORRADOR"
    assert len(data["lines"]) >= 2
    # SKU sintético
    assert all((ln.get("supplier_sku") or "").startswith("POP-") for ln in data["lines"])  
