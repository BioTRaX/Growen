#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: cleanup_logs.py
# NG-HEADER: Ubicación: scripts/cleanup_logs.py
# NG-HEADER: Descripción: Previsualiza y ejecuta la limpieza segura de logs físicos y ejecuciones de desarrollo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.logging.log_cleanup import build_cleanup_plan, execute_cleanup_plan  # noqa: E402


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def cleanup_screenshots(log_root: Path, *, keep_days: int, max_mb: int, dry_run: bool) -> tuple[int, int]:
    directory = log_root / "bugreport_screenshots"
    if not directory.exists() or (keep_days <= 0 and max_mb <= 0):
        return 0, 0
    import time

    files = sorted((path for path in directory.iterdir() if path.is_file()), key=lambda path: path.stat().st_mtime)
    selected: list[Path] = []
    if keep_days > 0:
        cutoff = time.time() - keep_days * 86400
        selected.extend(path for path in files if path.stat().st_mtime < cutoff)
    remaining = [path for path in files if path not in selected]
    if max_mb > 0:
        maximum = max_mb * 1024 * 1024
        total = sum(path.stat().st_size for path in remaining)
        for path in remaining:
            if total <= maximum:
                break
            selected.append(path)
            total -= path.stat().st_size
    freed = sum(path.stat().st_size for path in selected)
    for path in selected:
        print(f" - captura: {path.relative_to(log_root)}")
        if not dry_run:
            path.unlink(missing_ok=True)
    return len(selected), freed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Limpieza segura de logs de Growen")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar el plan sin modificar archivos")
    parser.add_argument("--keep-days", type=int, default=7, help="Conservar logs de los últimos N días; 0 selecciona todo lo no protegido")
    parser.add_argument("--include-latest-dev-run", action="store_true", help="Incluir la última carpeta dev si no tiene procesos activos")
    parser.add_argument("--skip-truncate", action="store_true", help="No truncar logs/backend.log")
    parser.add_argument("--screenshots-keep-days", type=int, default=0, help="Retención explícita de capturas; 0 no las modifica")
    parser.add_argument("--screenshots-max-mb", type=int, default=0, help="Límite explícito de capturas; 0 no las modifica")
    parser.add_argument("--log-root", type=Path, default=ROOT / "logs", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.keep_days < 0 or args.screenshots_keep_days < 0 or args.screenshots_max_mb < 0:
        parser.error("Los valores de retención no pueden ser negativos")

    log_root = args.log_root.resolve()
    plan = build_cleanup_plan(
        log_root=log_root,
        keep_days=args.keep_days,
        preserve_latest_dev_run=not args.include_latest_dev_run,
    )
    if args.skip_truncate:
        plan["targets"] = [target for target in plan["targets"] if target["kind"] != "truncate"]
        plan["target_count"] = len(plan["targets"])
        plan["bytes_reclaimable"] = sum(int(target["size_bytes"]) for target in plan["targets"])

    print(f"Directorio: {log_root}")
    print(f"Objetivos: {plan['target_count']} ({human_size(int(plan['bytes_reclaimable']))})")
    for target in plan["targets"]:
        print(f" - {target['kind']}: {target['path']}")
    for protected in plan["protected"]:
        print(f" - protegido: {protected['path']} ({protected['reason']})")

    screenshot_count, screenshot_bytes = cleanup_screenshots(
        log_root,
        keep_days=args.screenshots_keep_days,
        max_mb=args.screenshots_max_mb,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("--dry-run activo: no se modificó ningún archivo ni directorio.")
        return 0

    result = execute_cleanup_plan(plan, log_root=log_root)
    print(
        "Eliminados: "
        f"{result['removed_files']} archivos, {result['removed_directories']} carpetas dev; "
        f"truncados: {result['truncated_files']}; liberado: {human_size(int(result['bytes_reclaimed']))}."
    )
    if screenshot_count:
        print(f"Capturas eliminadas: {screenshot_count} ({human_size(screenshot_bytes)}).")
    for error in result["errors"]:
        print(f"ERROR {error['path']}: {error['error']}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
