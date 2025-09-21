#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: extract_eml_attachments.py
# NG-HEADER: Ubicación: scripts/extract_eml_attachments.py
# NG-HEADER: Descripción: Extrae adjuntos (PDF) desde un archivo .eml hacia una carpeta destino
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Extractor simple de adjuntos PDF desde correos .eml

Uso (ejemplos):
  - python scripts/extract_eml_attachments.py --eml "C:/Users/<usuario>/Downloads/Pedido 488344 Completado.eml"
  - python scripts/extract_eml_attachments.py --eml "./POP_remito_2025-09-18.eml" --out-dir "data/inbox/pop"

Descripción:
  - Lee un archivo .eml local y extrae todos los adjuntos PDF a la carpeta destino (por defecto: data/inbox/pop).
  - Respeta el nombre de archivo del adjunto; si ya existe, agrega sufijo _1, _2, ...
  - No requiere acceso a la API ni autenticación; sirve como paso previo para usar el importador de PDF en la UI.

Notas:
  - Soporta content-types típicos (application/pdf), y también adjuntos con application/octet-stream cuyo nombre termine en .pdf.
  - Sanitiza el nombre de archivo para evitar problemas de path traversal.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple
import email
from email import policy
from email.message import Message
import re


def _safe_filename(name: str | None, fallback: str = "adjunto.pdf") -> str:
    name = (name or fallback).strip()
    # Quitar directorios y caracteres problemáticos
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w\-. ]+", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name or fallback


def _unique_path(root: Path, filename: str) -> Path:
    p = root / filename
    if not p.exists():
        return p
    stem = p.stem
    suffix = p.suffix
    i = 1
    while True:
        cand = root / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def extract_pdf_attachments(eml_path: Path, out_dir: Path) -> Tuple[int, list[Path]]:
    data = eml_path.read_bytes()
    msg: Message = email.message_from_bytes(data, policy=policy.default)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    count = 0
    for part in msg.walk():
        cdisp = (part.get_content_disposition() or "").lower()
        ctype = (part.get_content_type() or "").lower()
        if cdisp != "attachment":
            continue
        fname = part.get_filename()
        looks_pdf = (
            ctype == "application/pdf"
            or (ctype == "application/octet-stream" and str(fname or "").lower().endswith(".pdf"))
        )
        if not looks_pdf:
            continue
        safe_name = _safe_filename(fname)
        target = _unique_path(out_dir, safe_name)
        payload = part.get_payload(decode=True) or b""
        target.write_bytes(payload)
        saved.append(target)
        count += 1
    return count, saved


def main():
    ap = argparse.ArgumentParser(description="Extrae adjuntos PDF desde un archivo .eml")
    ap.add_argument("--eml", required=True, help="Ruta al archivo .eml")
    ap.add_argument("--out-dir", default=str(Path("data") / "inbox" / "pop"), help="Directorio de salida (por defecto data/inbox/pop)")
    args = ap.parse_args()

    eml_path = Path(args.eml)
    if not eml_path.exists():
        raise SystemExit(f"No existe el archivo .eml: {eml_path}")
    out_dir = Path(args.out_dir)
    n, files = extract_pdf_attachments(eml_path, out_dir)
    if n == 0:
        print("No se encontraron adjuntos PDF en el .eml")
    else:
        print(f"Se extrajeron {n} PDF(s):")
        for p in files:
            print(f" - {p}")
        print("Ahora podés importar esos PDF desde la app (Compras → Importar PDF).")


if __name__ == "__main__":
    main()
