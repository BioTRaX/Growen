#!/usr/bin/env python
"""Quick smoke test for canonical auto-SKU generation.

Runs entirely in-memory using TestClient and sqlite aiosqlite memory DB.
"""
import os
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from fastapi.testclient import TestClient
from services.api import app
from services.auth import current_session, require_csrf, SessionData

# Bypass auth/CSRF for local smoke
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None

client = TestClient(app)

# 1) Create canonical without sku_custom
r = client.post("/canonical-products", json={"name": "ABono Orgánico"})
print("Status:", r.status_code)
print("Body:", r.json())
assert r.status_code == 200, r.text
body = r.json()
assert body.get("id") and body.get("ng_sku", "").startswith("NG-"), body
assert body.get("sku_custom") and len(body["sku_custom"]) >= 10, body

# 2) Ensure sequence increments for same category
r_cat = client.post("/categories", json={"name": "Fertilizantes"})
if r_cat.status_code == 200:
    cat = r_cat.json()
else:
    # already exists; list to find
    lr = client.get("/categories")
    cat = next(c for c in lr.json() if c.get("name") == "Fertilizantes" and c.get("parent_id") is None)

r1 = client.post("/canonical-products", json={"name": "Liquido X", "category_id": cat["id"]})
r2 = client.post("/canonical-products", json={"name": "Liquido Y", "category_id": cat["id"]})
assert r1.status_code == 200 and r2.status_code == 200
s1 = r1.json()["sku_custom"]
s2 = r2.json()["sku_custom"]
print("Seqs:", s1, s2)
assert s1.split("_")[1] == "0001" and s2.split("_")[1] == "0002"

print("OK: canonical auto-SKU smoke passed")
