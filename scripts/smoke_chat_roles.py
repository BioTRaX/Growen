#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_chat_roles.py
# NG-HEADER: Ubicación: scripts/smoke_chat_roles.py
# NG-HEADER: Descripción: Smoke autenticado HTTP y WebSocket para los cinco roles de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from websockets.asyncio.client import connect

ROLES = ("guest", "cliente", "proveedor", "colaborador", "admin")
PUBLIC_ROLES = {"guest", "cliente", "proveedor"}
FORBIDDEN_PUBLIC_KEYS = {"sku", "supplier_sku", "unique_sku", "stock", "stock_qty", "exact_stock"}


def _contains_forbidden(value) -> bool:
    if isinstance(value, dict):
        return bool(FORBIDDEN_PUBLIC_KEYS & {str(key).lower() for key in value}) or any(_contains_forbidden(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    return False


async def smoke_role(base_url: str, role: str, credential: dict) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=45, follow_redirects=False) as client:
        if role == "guest":
            response = await client.post("/auth/guest")
        else:
            response = await client.post("/auth/login", json={"identifier": credential["identifier"], "password": credential["password"]})
        response.raise_for_status()
        me = await client.get("/auth/me")
        me.raise_for_status()
        if me.json().get("role") != role:
            raise RuntimeError(f"smoke_role_mismatch_{role}")
        csrf = client.cookies.get("csrf_token")
        headers = {"X-CSRF-Token": csrf} if csrf else {}
        chat = await client.post("/chat", json={"text": "¿Qué disponibilidad pública hay?"}, headers=headers)
        chat.raise_for_status()
        payload = chat.json()
        if not payload.get("correlation_id"):
            raise RuntimeError(f"smoke_http_correlation_missing_{role}")
        if role in PUBLIC_ROLES and _contains_forbidden(payload.get("data")):
            raise RuntimeError(f"smoke_public_data_leak_{role}")

        parsed = urlparse(base_url)
        cookie = "; ".join(f"{key}={value}" for key, value in client.cookies.items())
        async with connect(f"{'wss' if parsed.scheme == 'https' else 'ws'}://{parsed.netloc}/ws", additional_headers={"Cookie": cookie}) as websocket:
            await websocket.send("hola")
            ws_payload = json.loads(await websocket.recv())
        if not ws_payload.get("correlation_id"):
            raise RuntimeError(f"smoke_ws_correlation_missing_{role}")
        if role == "admin":
            rollout = await client.get("/admin/chat-rollout")
            rollout.raise_for_status()
        return {"role": role, "http": "passed", "websocket": "passed"}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--credentials-file", required=True, type=Path)
    args = parser.parse_args()
    credentials_path = args.credentials_file.resolve()
    if not credentials_path.is_absolute() or credentials_path.is_symlink() or not credentials_path.is_file():
        raise SystemExit("credentials_file_invalid")
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    results = []
    for role in ROLES:
        if role != "guest" and role not in credentials:
            raise SystemExit(f"missing_smoke_credentials_{role}")
        results.append(await smoke_role(args.base_url.rstrip("/"), role, credentials.get(role, {})))
    print(json.dumps({"passed": True, "roles": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
