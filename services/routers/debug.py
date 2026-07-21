# NG-HEADER: Nombre de archivo: debug.py
# NG-HEADER: Ubicación: services/routers/debug.py
# NG-HEADER: Descripción: Rutas de depuración, salud y limpieza de logs fuera de producción.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import io
import os
import re
from contextlib import redirect_stdout
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends

from db.session import engine
from services.auth import require_csrf, require_roles
from services.logging.log_cleanup import build_cleanup_plan, execute_cleanup_plan
from services.suppliers.parsers import SUPPLIER_PARSERS


router = APIRouter()


if os.getenv("ENV", "dev") != "production":
    admin_only = [Depends(require_roles("admin"))]

    @router.get("/healthz", dependencies=admin_only)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/debug/db", dependencies=admin_only)
    async def debug_db() -> dict[str, object]:
        async with engine.connect() as conn:
            value = (await conn.exec_driver_sql("SELECT 1")).scalar()
        return {"ok": True, "select1": value}

    @router.get("/debug/config", dependencies=admin_only)
    async def debug_config() -> dict[str, object]:
        origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
        db_url = os.getenv("DB_URL", "")
        if db_url:
            parts = urlsplit(db_url)
            netloc = parts.netloc
            if "@" in netloc and ":" in netloc.split("@")[0]:
                user = netloc.split("@")[0].split(":")[0]
                host = netloc.split("@")[1]
                netloc = f"{user}:***@{host}"
            safe_url = parts._replace(netloc=netloc).geturl()
        else:
            safe_url = ""
        return {"allowed_origins": [origin.strip() for origin in origins if origin.strip()], "db_url": safe_url}

    @router.get("/debug/imports/doctor", dependencies=admin_only)
    async def debug_import_doctor() -> dict[str, object]:
        from tools.doctor import run_doctor

        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            all_ok = run_doctor()
        output = output_buffer.getvalue()
        results = []
        for line in output.splitlines():
            if line.startswith("---") or not line.strip():
                continue
            status, _, rest = line.partition(":")
            details = rest.strip()
            tool_match = re.search(r"'(.*?)'", details)
            version_match = re.search(r"Versión: (.*)", details)
            path_match = re.search(r"en '(.*?)'", details)
            error_match = re.search(r"no se encontró|tardó demasiado|Error al verificar", details)
            results.append({
                "tool": tool_match.group(1) if tool_match else "unknown",
                "status": status.strip(),
                "version": version_match.group(1) if version_match else None,
                "path": path_match.group(1) if path_match else None,
                "error": details if error_match else None,
            })
        return {"all_ok": all_ok, "raw_output": output, "results": results}

    @router.get("/debug/imports/parsers", dependencies=admin_only)
    async def debug_import_parsers() -> dict[str, list[str]]:
        return {"parsers": list(SUPPLIER_PARSERS.keys())}

    @router.post("/debug/clear-logs", dependencies=[Depends(require_roles("admin")), Depends(require_csrf)])
    async def clear_logs() -> dict[str, object]:
        """Alias legacy de la política canónica; preserva ejecuciones activas e historiales protegidos."""
        plan = build_cleanup_plan(keep_days=0)
        result = execute_cleanup_plan(plan)
        return {"status": "ok" if result["ok"] else "partial", "plan": plan, "result": result}
