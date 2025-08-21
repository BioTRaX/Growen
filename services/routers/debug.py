"""Endpoints de diagnóstico y salud."""

from fastapi import APIRouter, Depends
from db.session import engine
import os
from urllib.parse import urlsplit

from services.suppliers.parsers import SUPPLIER_PARSERS
from services.auth import require_roles

router = APIRouter()

if os.getenv("ENV", "dev") != "production":
    admin_only = [Depends(require_roles("admin"))]

    @router.get("/healthz", dependencies=admin_only)
    async def healthz() -> dict[str, str]:
        """Confirma que la aplicación está viva."""
        return {"status": "ok"}

    @router.get("/debug/db", dependencies=admin_only)
    async def debug_db() -> dict[str, object]:
        """Realiza un ``SELECT 1`` para verificar la conexión a la DB."""
        async with engine.connect() as conn:
            val = (await conn.exec_driver_sql("SELECT 1")).scalar()
        return {"ok": True, "select1": val}

    @router.get("/debug/config", dependencies=admin_only)
    async def debug_config() -> dict[str, object]:
        """Muestra configuración básica sin exponer credenciales sensibles."""
        origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
        db_url = os.getenv("DB_URL", "")
        if db_url:
            parts = urlsplit(db_url)
            netloc = parts.netloc
            if "@" in netloc and ":" in netloc.split("@")[0]:
                user = netloc.split("@")[0].split(":")[0]
                host = netloc.split("@")[1]
                netloc = f"{user}:***@{host}"
            safe = parts._replace(netloc=netloc).geturl()
        else:
            safe = ""
        return {
            "allowed_origins": [o.strip() for o in origins if o.strip()],
            "db_url": safe,
        }

    @router.get("/debug/imports/parsers", dependencies=admin_only)
    async def debug_import_parsers() -> dict[str, list[str]]:
        """Lista los parsers de proveedores registrados."""
        return {"parsers": list(SUPPLIER_PARSERS.keys())}

