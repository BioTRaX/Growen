#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_login_flow.py
# NG-HEADER: Ubicación: scripts/test_login_flow.py
# NG-HEADER: Descripción: Smoke autenticado sin credenciales ni cookies hardcodeadas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
import sys
import time

import requests
from dotenv import load_dotenv


def _check(response: requests.Response, label: str, expected: int = 200) -> dict:
    print(f"{label}: {response.status_code}")
    if response.status_code != expected:
        raise RuntimeError(f"{label} devolvió {response.status_code}: {response.text[:300]}")
    return response.json()


def main() -> int:
    load_dotenv()
    base = os.getenv("SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    identifier = os.getenv("ADMIN_USER")
    password = os.getenv("ADMIN_PASS")
    if not identifier or not password:
        print("Faltan ADMIN_USER/ADMIN_PASS en el entorno.", file=sys.stderr)
        return 2

    session = requests.Session()
    session.headers["Origin"] = os.getenv("SMOKE_ORIGIN", "http://127.0.0.1:5176")
    session.headers["User-Agent"] = "growen-authenticated-smoke/1.0"

    _check(session.get(f"{base}/health", timeout=15), "health")
    _check(
        session.post(
            f"{base}/auth/login",
            json={"identifier": identifier, "password": password},
            timeout=20,
        ),
        "login",
    )
    me = _check(session.get(f"{base}/auth/me", timeout=15), "auth/me")
    if not me.get("is_authenticated") or me.get("role") not in {"admin", "colaborador"}:
        raise RuntimeError("La sesión no quedó autenticada con rol staff")
    print(f"rol autenticado: {me['role']}")

    market = _check(session.get(f"{base}/market/products?page=1&page_size=1", timeout=20), "market")
    items = market.get("items") or []
    if items:
        canonical_id = items[0]["product_id"]
        knowledge = _check(
            session.get(f"{base}/canonical-products/{canonical_id}/knowledge", timeout=20),
            "conocimiento",
        )
        print(f"conocimiento: {knowledge['summary']['total']} activos")
        if os.getenv("SMOKE_PROCESS_KNOWLEDGE", "0") == "1" and knowledge.get("items"):
            asset_id = knowledge["items"][0]["id"]
            csrf = session.cookies.get("csrf_token")
            if not csrf:
                raise RuntimeError("La sesión autenticada no entregó cookie CSRF")
            queued = _check(
                session.post(
                    f"{base}/canonical-products/{canonical_id}/knowledge/{asset_id}/process",
                    headers={"X-CSRF-Token": csrf},
                    timeout=20,
                ),
                "encolar conocimiento",
                expected=202,
            )
            job_id = queued["job_id"]
            terminal = None
            for _ in range(60):
                jobs = _check(
                    session.get(f"{base}/canonical-products/{canonical_id}/knowledge/jobs", timeout=15),
                    "poll conocimiento",
                )
                current = next((item for item in jobs.get("items", []) if item["id"] == job_id), None)
                if current and current["status"] in {"completed", "failed", "cancelled"}:
                    terminal = current
                    break
                time.sleep(1)
            if not terminal:
                raise RuntimeError(f"El job {job_id} no alcanzó estado terminal")
            if terminal["status"] != "completed":
                raise RuntimeError(f"El job {job_id} terminó en {terminal['status']}: {terminal.get('error')}")
            print(f"job conocimiento: {job_id} completed")
    _check(session.get(f"{base}/health/knowledge-worker", timeout=15), "knowledge-worker")
    print("smoke autenticado: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
