#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_notion_sections.py
# NG-HEADER: Ubicación: scripts/smoke_notion_sections.py
# NG-HEADER: Descripción: Smoke test del flujo Notion en modo 'sections' (dry-run por defecto)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
from dotenv import load_dotenv
import sys
from pathlib import Path


def main() -> int:
    # Asegurar import de paquetes locales
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    load_dotenv()
    # Forzar modo sections y dry-run si no está definido
    os.environ.setdefault("NOTION_MODE", "sections")
    os.environ.setdefault("NOTION_DRY_RUN", "1")

    from services.integrations.notion_sections import upsert_report_as_child, derive_section_from_url

    cfg = {
        "enabled": os.getenv("NOTION_FEATURE_ENABLED"),
        "mode": os.getenv("NOTION_MODE"),
        "dry_run": os.getenv("NOTION_DRY_RUN"),
        "db": os.getenv("NOTION_ERRORS_DATABASE_ID"),
    }
    print("[smoke] cfg:", cfg)

    urls = [
        "http://localhost:5173/compras/lista",
        "http://localhost:5173/stock/lista",
        "http://localhost:5173/app/home",
    ]
    for u in urls:
        sec = derive_section_from_url(u)
        res = upsert_report_as_child(u, f"Smoke for {sec}")
        print(f"[smoke] url={u} -> section={sec} res={res}")

    print("[smoke] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
