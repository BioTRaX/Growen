# NG-HEADER: Nombre de archivo: logs.py
# NG-HEADER: Ubicación: tools/logs.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Utilities to purge or rotate project logs.

Usage:
  python -m tools.logs --purge
  python -m tools.logs --rotate
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"


def purge() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    removed = 0
    for p in LOGS.glob("**/*"):
        try:
            if p.is_file():
                p.unlink()
                removed += 1
        except Exception:
            pass
    print(f"Purged {removed} files from {LOGS}")
    return 0


def rotate() -> int:
    # Touch a marker file to indicate rotation asked; actual handlers rotate by size/time.
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / ".rotate-request").write_text("1", encoding="utf-8")
    print("Rotation requested (handlers rotate by size/time).")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--rotate", action="store_true")
    args = ap.parse_args(argv)
    if args.purge:
        return purge()
    if args.rotate:
        return rotate()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

