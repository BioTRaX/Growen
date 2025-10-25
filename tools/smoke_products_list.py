#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_products_list.py
# NG-HEADER: Ubicación: tools/smoke_products_list.py
# NG-HEADER: Descripción: Smoke test: login y GET /products para verificar resultados
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import sys
import json
import requests

BASE = os.environ.get('GROWEN_BASE', 'http://127.0.0.1:8000')
USER = os.environ.get('ADMIN_USER', 'admin')
PASS = os.environ.get('ADMIN_PASS', 'admin123')

s = requests.Session()

# login
r = s.post(f"{BASE}/auth/login", json={"identifier": USER, "password": PASS})
print("LOGIN:", r.status_code)
if r.status_code != 200:
    print("Body:", r.text[:500])
    sys.exit(1)

# list products
r = s.get(f"{BASE}/products", params={"type": "all", "page": 1}, timeout=20)
print("GET /products:", r.status_code)
if r.status_code != 200:
    print("Body:", r.text[:500])
    sys.exit(2)

try:
    j = r.json()
except Exception as e:
    print("Invalid JSON:", e)
    print(r.text[:1000])
    sys.exit(3)

print("TOTAL:", j.get('total'))
print("ITEMS_LEN:", len(j.get('items') or []))
print("SAMPLE:", json.dumps((j.get('items') or [])[:2], ensure_ascii=False))
