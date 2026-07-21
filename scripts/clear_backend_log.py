#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: clear_backend_log.py
# NG-HEADER: Ubicación: scripts/clear_backend_log.py
# NG-HEADER: Descripción: Trunca exclusivamente logs/backend.log sin afectar historiales protegidos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.logging.log_cleanup import execute_cleanup_plan  # noqa: E402


def main() -> int:
    log_root = ROOT / "logs"
    backend = log_root / "backend.log"
    if not backend.exists():
        print(f"No existe: {backend}")
        return 0
    plan = {
        "log_root": str(log_root),
        "targets": [{"path": "backend.log", "kind": "truncate", "size_bytes": backend.stat().st_size, "reason": "limpieza específica"}],
        "protected": [],
    }
    result = execute_cleanup_plan(plan, log_root=log_root)
    if result["ok"]:
        print(f"Truncado: {backend}")
        return 0
    for error in result["errors"]:
        print(f"ERROR {error['path']}: {error['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
