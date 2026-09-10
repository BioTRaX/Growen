#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_login_flow.py
# NG-HEADER: Ubicación: scripts/test_login_flow.py
# NG-HEADER: Descripción: Smoke autenticado sin credenciales ni cookies hardcodeadas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
from pathlib import Path
import sys
import time

import requests
from dotenv import load_dotenv


def _read_credential(name: str) -> str:
    file_name = f"{name}_FILE"
    configured_path = os.getenv(file_name, "").strip()
    if configured_path:
        path = Path(configured_path).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"{file_name} no apunta a un archivo regular")
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
        if not value:
            raise RuntimeError(f"{file_name} está vacío")
        return value
    if os.getenv("SMOKE_ALLOW_DIRECT_CREDENTIALS", "0") == "1":
        value = os.getenv(name, "")
        if value:
            return value
    raise RuntimeError(f"Falta {file_name}; las credenciales directas están deshabilitadas")


def _build_session(base: str) -> requests.Session:
    ca_bundle = os.getenv("SMOKE_CA_BUNDLE", "").strip()
    if not ca_bundle:
        raise RuntimeError("Falta SMOKE_CA_BUNDLE")
    ca_path = Path(ca_bundle).expanduser().resolve()
    if not ca_path.is_file():
        raise RuntimeError("SMOKE_CA_BUNDLE no apunta a un archivo regular")
    session = requests.Session()
    session.verify = str(ca_path)
    session.headers["Origin"] = os.getenv("SMOKE_ORIGIN", base)
    session.headers["User-Agent"] = "growen-authenticated-smoke/1.0"
    return session


def _check_security_headers(response: requests.Response) -> None:
    required = {
        "content-security-policy",
        "strict-transport-security",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
    }
    missing = sorted(required.difference(name.lower() for name in response.headers))
    if missing:
        raise RuntimeError(f"Faltan cabeceras defensivas: {', '.join(missing)}")


def _check(response: requests.Response, label: str, expected: int = 200) -> dict:
    print(f"{label}: {response.status_code}")
    if response.status_code != expected:
        raise RuntimeError(f"{label} devolvió {response.status_code}: {response.text[:300]}")
    return response.json()


def main() -> int:
    load_dotenv()
    base = os.getenv("SMOKE_API_URL", "https://192.168.100.100").rstrip("/")
    if not base.startswith("https://"):
        print("SMOKE_API_URL debe usar HTTPS.", file=sys.stderr)
        return 2
    try:
        identifier = _read_credential("ADMIN_USER")
        password = _read_credential("ADMIN_PASS")
        session = _build_session(base)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    health_response = session.get(f"{base}/health", timeout=15)
    _check(health_response, "health")
    _check_security_headers(health_response)
    for path in ("/debug/frontend/env", "/auth/debug/sessions"):
        response = session.get(f"{base}{path}", timeout=15)
        if response.status_code != 404:
            raise RuntimeError(f"{path} debe devolver 404 en producción")
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
    session_cookie = session.cookies.get("growen_session")
    if not session_cookie:
        raise RuntimeError("El login no entregó la cookie de sesión")
    set_cookie = session.cookies.get_dict()
    if "csrf_token" not in set_cookie:
        raise RuntimeError("El login no entregó cookie CSRF")
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
