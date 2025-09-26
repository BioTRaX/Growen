# NG-HEADER: Nombre de archivo: report.py
# NG-HEADER: Ubicación: services/ingest/report.py
# NG-HEADER: Descripción: Genera reportes y métricas del pipeline de ingesta.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Generación simple de reportes."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Dict, Any


def write_reports(job_id: str, changes: Iterable[Dict[str, Any]], errors: Iterable[Dict[str, Any]], dest: str | Path = "data/reports") -> None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    changes = list(changes)
    errors = list(errors)
    summary = {"changes": len(changes), "errors": len(errors)}
    with open(dest / f"import_{job_id}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f)
    changes_path = dest / f"import_{job_id}_changes.csv"
    with open(changes_path, "w", newline="", encoding="utf-8") as f:
        if changes:
            writer = csv.DictWriter(f, fieldnames=changes[0].keys())
            writer.writeheader()
            writer.writerows(changes)
        else:
            f.write("")
    errors_path = dest / f"import_{job_id}_errors.csv"
    with open(errors_path, "w", newline="", encoding="utf-8") as f:
        if errors:
            writer = csv.DictWriter(f, fieldnames=errors[0].keys())
            writer.writeheader()
            writer.writerows(errors)
        else:
            f.write("")
