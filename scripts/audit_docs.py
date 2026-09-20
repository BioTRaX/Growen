#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: audit_docs.py
# NG-HEADER: Ubicación: scripts/audit_docs.py
# NG-HEADER: Descripción: Auditoría de encabezados, enlaces, duplicidad y referencias obsoletas.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = "<!-- NG-HEADER:"
STALE = (
    "FEATURES_PENDIENTES.md",
    "MARKET_ALERTS_QUICK_START.md",
    "growen.db",
)


def audit(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    docs = [
        p
        for p in root.rglob("*.md")
        if ".git" not in p.parts
        and "node_modules" not in p.parts
        and ".venv" not in p.parts
        and "Promps" not in p.parts
        and ".agents" not in p.parts
        and ".agent" not in p.parts
        and p.name != "ollama_readme.md"
        and (p.parent == root or "docs" in p.parts)
    ]
    active = [p for p in docs if "archive" not in p.parts and "superpowers" not in p.parts]
    for path in active:
        if path.name != "README.md" and not path.read_text(encoding="utf-8-sig").lstrip().startswith(HEADER):
            errors.append(f"header_missing:{path.relative_to(root)}")
        text = path.read_text(encoding="utf-8-sig")
        for target in re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            candidate = (path.parent / target).resolve()
            if not candidate.exists():
                errors.append(f"link_missing:{path.relative_to(root)}->{target}")
        for term in STALE:
            if term in text:
                errors.append(f"stale_reference:{path.relative_to(root)}:{term}")
    hashes: dict[str, Path] = {}
    for path in active:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            errors.append(f"duplicate:{hashes[digest].relative_to(root)}=={path.relative_to(root)}")
        else:
            hashes[digest] = path
    return errors


if __name__ == "__main__":
    findings = audit()
    for finding in findings:
        print(finding)
    raise SystemExit(1 if findings else 0)
