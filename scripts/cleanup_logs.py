#!/usr/bin/env python
"""Utilidad para limpiar logs históricos dejando un arranque limpio.

Acciones:
- Elimina archivos *.bak en logs/backend.* y backend.log.* dentro de logs/
- Trunca (no elimina) logs/backend.log si existe
- Elimina archivos *.log dentro de logs/catalog/ (si existiera) y subcarpetas diagnostics
- Elimina archivos de logs de jobs de imágenes (image_jobs*.log) si existieran
- Mantiene estructura de directorios.

Uso:
  python scripts/cleanup_logs.py [--dry-run] [--keep-days N]

--dry-run   Muestra lo que se haría sin modificar nada.
--keep-days Conserva archivos cuyo mtime es más reciente que N días (por defecto 0 => borra todos los coincidentes).

Salida con códigos:
  0 Exitoso
  1 Error inesperado
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"

PATTERNS = [
    "backend.log.*.bak",
    "backend.log.*",
    "*.catalog_diagnostics_detail.log",
    "*.catalog_diagnostics_summary.log",
    "image_jobs*.log",
]

# Directorios adicionales que podrían contener logs secundarios
EXTRA_DIRS = [
    LOGS_DIR / "diagnostics",
]


def human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}TB"


def collect_files(keep_days: int) -> list[Path]:
    cutoff = time.time() - keep_days * 86400
    results: list[Path] = []

    def consider(p: Path):
        if not p.is_file():
            return
        try:
            if keep_days > 0 and p.stat().st_mtime >= cutoff:
                return
        except OSError:
            return
        results.append(p)

    # Principal
    if LOGS_DIR.exists():
        for pattern in PATTERNS:
            for p in LOGS_DIR.glob(pattern):
                if p.name == "backend.log":  # no eliminar archivo principal
                    continue
                consider(p)
    for d in EXTRA_DIRS:
        if d.exists():
            for pattern in PATTERNS:
                for p in d.glob(pattern):
                    consider(p)
    return results


def truncate_backend(skip: bool = False):
    main_log = LOGS_DIR / "backend.log"
    if not main_log.exists():
        return False, 0
    if skip:
        return False, main_log.stat().st_size
    size = main_log.stat().st_size
    try:
        with open(main_log, "w", encoding="utf-8"):
            pass
        return True, size
    except PermissionError:
        # En Windows puede estar bloqueado por un proceso (uvicorn). Dejar marcador y continuar.
        marker = LOGS_DIR / "backend.log.cleared"
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("clear-intent: failed due to lock; please stop server and re-run cleanup\n")
        except OSError:
            pass
        return False, size


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Solo mostrar acciones")
    ap.add_argument("--keep-days", type=int, default=0, help="Conservar archivos modificados en los últimos N días")
    ap.add_argument("--skip-truncate", action="store_true", help="No truncar backend.log (evita error si está bloqueado)")
    args = ap.parse_args(argv)

    if not LOGS_DIR.exists():
        print(f"No existe directorio de logs: {LOGS_DIR}")
        return 0

    targets = collect_files(args.keep_days)
    total_bytes = 0
    for f in targets:
        try:
            total_bytes += f.stat().st_size
        except OSError:
            pass

    # Evitar caracteres no ASCII en Windows (como '≈') para no romper stdout por encoding
    approx = "~"
    print(f"Encontrados {len(targets)} archivos para eliminar ({approx} {human_size(total_bytes)})")
    for f in targets:
        print(f" - {f.relative_to(ROOT)}")

    if args.dry_run:
        print("--dry-run activo: no se eliminarán archivos.")
    else:
        deleted = 0
        for f in targets:
            try:
                f.unlink()
                deleted += 1
            except OSError as e:
                print(f"No se pudo eliminar {f}: {e}")
        print(f"Eliminados {deleted} archivos.")

    truncated, prev = truncate_backend(skip=args.skip_truncate)
    if truncated:
        print(f"Truncado backend.log (antes {human_size(prev)})")
    else:
        if (LOGS_DIR / "backend.log").exists():
            print("backend.log no truncado (posible bloqueo); se dejó marcador backend.log.cleared")
        else:
            print("backend.log no existe, nada que truncar")

    print("Listo.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
