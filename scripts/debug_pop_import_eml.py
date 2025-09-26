#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: debug_pop_import_eml.py
# NG-HEADER: Ubicación: scripts/debug_pop_import_eml.py
# NG-HEADER: Descripción: Script de depuración para importar POP desde .eml y mostrar parse_debug
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations
import os
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _ensure_supplier_pop() -> int:
    # Buscar POP; si no existe, crearlo
    r = client.get("/suppliers")
    if r.status_code == 200:
        for s in r.json():
            if (s.get("slug") or "").lower() == "pop":
                return s["id"]
    r = client.post("/suppliers", json={"slug": "pop", "name": "POP"})
    assert r.status_code in (200, 201), r.text
    sid = client.get("/suppliers").json()[0]["id"]
    return sid


def main():
    eml_path = Path(os.environ.get("DEBUG_POP_EML", str(Path("Devs") / "Pedido 488344 Completado.eml")))
    assert eml_path.exists(), f"No existe .eml en {eml_path} (setea DEBUG_POP_EML)"
    supplier_id = _ensure_supplier_pop()
    with eml_path.open("rb") as fh:
        files = {"file": (eml_path.name, fh, "message/rfc822")}
        r = client.post(f"/purchases/import/pop-email?supplier_id={supplier_id}&kind=eml", files=files)
    print("status:", r.status_code)
    try:
        data = r.json()
    except Exception:
        print(r.text)
        raise
    print("response:", data)
    pid = data.get("purchase_id")
    if pid:
        g = client.get(f"/purchases/{pid}")
        pdata = g.json()
        print("lines:", len(pdata.get("lines") or []))
        for i, ln in enumerate(pdata.get("lines") or [], 1):
            print(f"[{i}] qty={ln.get('qty')} unit={ln.get('unit_cost')} sku={ln.get('supplier_sku')} title={ln.get('title')}")
        # logs
        lg = client.get(f"/purchases/{pid}/logs?limit=50")
        for ev in (lg.json() or [])[::-1]:
            if ev.get("action") == "purchase_import_pop_email":
                print("parse_debug:", ev.get("meta", {}).get("parse_debug"))
                break


if __name__ == "__main__":
    main()
