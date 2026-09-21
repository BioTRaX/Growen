#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_media_permissions.py
# NG-HEADER: Ubicación: scripts/check_media_permissions.py
# NG-HEADER: Descripción: Verifica permisos de lectura y escritura en los volúmenes de media configurados.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script de diagnóstico para verificar que las raíces de media públicas y privadas sean escribibles."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Asegurar importación de settings de Growen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from agent_core.config import settings
    from services.media import get_public_media_root, get_private_media_root
except Exception as exc:
    print(f"[ERROR] No se pudo importar la configuración de Growen: {exc}", file=sys.stderr)
    sys.exit(1)


def check_directory(path: Path, label: str) -> bool:
    print(f"[*] Verificando {label}: {path}")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"  [FALLO] No se pudo crear/acceder al directorio {path}: {exc}", file=sys.stderr)
        return False

    # Probar escritura de archivo temporal
    probe_file = path / f".probe_{uuid.uuid4().hex}.tmp"
    try:
        with open(probe_file, "w", encoding="utf-8") as fh:
            fh.write("write_probe_ok\n")
        probe_file.unlink(missing_ok=True)
        print(f"  [OK] Permiso de escritura confirmado en {path}")
        return True
    except PermissionError as exc:
        print(
            f"  [FALLO] PermissionError en {path}: {exc}\n"
            f"          Sugerencia para Docker: docker exec -u 0 <container_id> chown -R app:app /data/media",
            file=sys.stderr,
        )
        return False
    except Exception as exc:
        print(f"  [FALLO] Error inesperado en {path}: {exc}", file=sys.stderr)
        return False


def main() -> int:
    public_root = get_public_media_root()
    private_root = get_private_media_root()

    ok_public = check_directory(public_root, "PUBLIC_MEDIA_ROOT")
    ok_private = check_directory(private_root, "PRIVATE_MEDIA_ROOT")

    # Verificar subdirectorio compras/_tmp específicamente
    purchases_tmp = private_root / "purchases" / "_tmp"
    ok_tmp = check_directory(purchases_tmp, "PRIVATE_MEDIA_ROOT/purchases/_tmp")

    if ok_public and ok_private and ok_tmp:
        print("[SUCCESS] Todos los directorios de media son escribibles.")
        return 0
    else:
        print("[ERROR] Uno o más directorios de media no tienen permisos de escritura.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
