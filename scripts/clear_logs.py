#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: clear_logs.py
# NG-HEADER: Ubicación: scripts/clear_logs.py
# NG-HEADER: Descripción: Adaptador legacy para limpiar todos los logs no protegidos mediante la política canónica.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import sys

from cleanup_logs import main


if __name__ == "__main__":
    print("Aviso: clear_logs.py es un alias legacy; se recomienda cleanup_logs.py --dry-run.")
    raise SystemExit(main(["--keep-days", "0", "--include-latest-dev-run", *sys.argv[1:]]))
