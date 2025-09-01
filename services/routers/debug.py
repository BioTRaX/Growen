# NG-HEADER: Nombre de archivo: debug.py
# NG-HEADER: Ubicación: services/routers/debug.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints de diagnóstico y salud."""

from fastapi import APIRouter, Depends
from db.session import engine
import os
from urllib.parse import urlsplit
from pathlib import Path

from services.suppliers.parsers import SUPPLIER_PARSERS
from services.auth import require_roles, require_csrf

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

    @router.post("/debug/clear-logs", dependencies=[Depends(require_roles("admin")), Depends(require_csrf)])
    async def clear_logs() -> dict[str, object]:
        """Trunca logs comunes y limpia logs de migraciones.

        No detiene procesos; si algún archivo está bloqueado, lo reporta y continúa.
        """
        ROOT = Path(__file__).resolve().parents[2]
        LOGS = ROOT / "logs"
        LOGS.mkdir(parents=True, exist_ok=True)

        results: list[str] = []
        def _truncate_win32(p: Path) -> tuple[bool, str]:
            """Best-effort truncate using Win32 to bypass simple share locks.

            Returns (ok, message)
            """
            try:
                import ctypes
                from ctypes import wintypes

                GENERIC_WRITE = 0x40000000
                FILE_SHARE_READ = 0x00000001
                FILE_SHARE_WRITE = 0x00000002
                FILE_SHARE_DELETE = 0x00000004
                OPEN_EXISTING = 3
                FILE_ATTRIBUTE_NORMAL = 0x80
                FILE_BEGIN = 0

                CreateFileW = ctypes.windll.kernel32.CreateFileW
                CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                        wintypes.HANDLE]
                CreateFileW.restype = wintypes.HANDLE

                SetFilePointerEx = ctypes.windll.kernel32.SetFilePointerEx
                SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                             ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
                SetFilePointerEx.restype = wintypes.BOOL

                SetEndOfFile = ctypes.windll.kernel32.SetEndOfFile
                SetEndOfFile.argtypes = [wintypes.HANDLE]
                SetEndOfFile.restype = wintypes.BOOL

                CloseHandle = ctypes.windll.kernel32.CloseHandle
                CloseHandle.argtypes = [wintypes.HANDLE]
                CloseHandle.restype = wintypes.BOOL

                INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

                h = CreateFileW(str(p), GENERIC_WRITE,
                                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
                if h == INVALID_HANDLE_VALUE:
                    return False, "CreateFileW failed"
                try:
                    new_pos = ctypes.c_longlong(0)
                    if not SetFilePointerEx(h, 0, ctypes.byref(new_pos), FILE_BEGIN):
                        return False, "SetFilePointerEx failed"
                    if not SetEndOfFile(h):
                        return False, "SetEndOfFile failed"
                    return True, "cleared (win32)"
                finally:
                    CloseHandle(h)
            except Exception as e:  # pragma: no cover - best effort
                return False, f"win32 truncate error: {e}"

        def truncate_file(p: Path) -> str:
            # 1) Try normal truncate
            try:
                with open(p, "w", encoding="utf-8"):
                    pass
                return f"cleared: {p.name}"
            except PermissionError as e:
                # 2) Try ftruncate if we can obtain RW
                try:
                    with open(p, "r+b") as fh:
                        fh.truncate(0)
                    return f"cleared: {p.name}"
                except Exception:
                    # 3) On Windows, last resort via Win32 API
                    if os.name == "nt":
                        ok, msg = _truncate_win32(p)
                        if ok:
                            return f"cleared: {p.name}"
                        return f"skip (locked): {p.name} -> {msg}"
                    return f"skip (locked): {p.name} -> {e}"
            except Exception as e:
                return f"skip: {p.name} -> {e}"

        files = [
            LOGS / "backend.log",
            LOGS / "frontend.log",
            LOGS / "start.log",
            LOGS / "fix_deps.log",
            LOGS / "run_api.log",
        ]
        for f in files:
            if f.exists():
                results.append(truncate_file(f))
            else:
                try:
                    f.touch()
                    results.append(f"created: {f.name}")
                except Exception as e:
                    results.append(f"skip (create failed): {f.name} -> {e}")

        migdir = LOGS / "migrations"
        cleared = 0
        if migdir.exists():
            for child in migdir.glob("*"):
                try:
                    if child.is_file():
                        child.unlink()
                        cleared += 1
                except Exception as e:
                    results.append(f"skip (rm): {child.name} -> {e}")
        else:
            try:
                migdir.mkdir(parents=True, exist_ok=True)
                results.append("created migrations log dir")
            except Exception as e:
                results.append(f"skip (mkdir migrations): {e}")

        return {"status": "ok", "results": results, "migrations_cleared": cleared}

