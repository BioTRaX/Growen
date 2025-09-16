#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_pdf_crypto.py
# NG-HEADER: Ubicación: scripts/check_pdf_crypto.py
# NG-HEADER: Descripción: Inspección de PDFs para detectar tipo de cifrado (ARC4/RC4, AES) y estado
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Herramienta de inspección de PDFs para evaluar riesgos de cifrado legacy.

Uso:
  python scripts/check_pdf_crypto.py <ruta_o_directorio> [--recursive]

Salida:
  - Por cada PDF: algoritmo de cifrado (si aplica), longitud de clave, flags de permisos.
  - Código de salida 0 si no se detecta ARC4; 2 si se detecta ARC4 en algún PDF.

Requisitos: PyPDF2 o pypdf, pdfplumber opcional.
"""
from __future__ import annotations
import sys, os, argparse, json, hashlib
from pathlib import Path

try:
    from PyPDF2 import PdfReader  # type: ignore
except Exception:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"ERROR: No se pudo importar PyPDF2/pypdf: {e}", file=sys.stderr)
        sys.exit(1)


def inspect_pdf(path: Path) -> dict:
    info: dict = {"file": str(path), "encrypted": False}
    try:
        reader = PdfReader(str(path))
        if getattr(reader, 'is_encrypted', False):
            info["encrypted"] = True
            # Intentar sin contraseña (muchos PDFs permiten apertura sin owner pwd)
            try:
                if reader.is_encrypted:
                    reader.decrypt("")  # type: ignore[arg-type]
            except Exception:
                info["decrypt_attempt"] = "failed"
            # Heurística: PyPDF2/pypdf no siempre expone algoritmo directamente; buscar en raw xref
            raw = None
            try:
                # Esto es interno y puede romperse versión a versión
                raw = reader.trailer.get('/Encrypt')  # type: ignore
            except Exception:
                pass
            algo = None
            if isinstance(raw, dict):
                f = raw.get('/Filter')
                sub = raw.get('/SubFilter')
                v = raw.get('/V')
                r = raw.get('/R')
                length = raw.get('/Length')
                cf = raw.get('/CF')
                if r in (2, 3, 4) and (v in (1, 2) or (cf and 'StdCF' in cf)):
                    # Probable RC4
                    algo = 'RC4/ARC4' if length in (40, 128) else 'RC4-like'
                if v in (4, 5, 6) or (cf and any('AES' in str(x) for x in cf.keys())):
                    algo = 'AES'
                info.update({"pdf_V": v, "pdf_R": r, "pdf_Length": length, "algo": algo})
            if not algo:
                info["algo"] = "unknown"
        # Hash para integridad opcional
        h = hashlib.sha256()
        with open(path, 'rb') as fh:
            h.update(fh.read())
        info["sha256"] = h.hexdigest()
    except Exception as e:
        info["error"] = str(e)
    return info


def collect_pdfs(base: Path, recursive: bool) -> list[Path]:
    if base.is_file() and base.suffix.lower() == '.pdf':
        return [base]
    files = []
    pattern = '**/*.pdf' if recursive else '*.pdf'
    for p in base.glob(pattern):
        if p.is_file():
            files.append(p)
    return files


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='Ruta de archivo PDF o directorio')
    ap.add_argument('--recursive', action='store_true')
    ap.add_argument('--json', action='store_true', help='Salida JSON')
    args = ap.parse_args(argv)
    base = Path(args.path)
    if not base.exists():
        print('Ruta no existe', file=sys.stderr)
        return 1
    pdfs = collect_pdfs(base, args.recursive)
    results = []
    arc4_found = False
    for pdf in pdfs:
        info = inspect_pdf(pdf)
        if info.get('algo') in ('RC4/ARC4', 'RC4-like'):
            arc4_found = True
        results.append(info)
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"{r['file']} :: encrypted={r.get('encrypted')} algo={r.get('algo')} length={r.get('pdf_Length')} error={r.get('error')}")
    return 2 if arc4_found else 0

if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
