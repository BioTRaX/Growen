from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


def pdf_has_text(pdf_path: Path, min_chars: int = 100) -> bool:
    try:
        import pdfplumber  # type: ignore
        chars = 0
        with pdfplumber.open(str(pdf_path)) as pdf:
            for p in pdf.pages:
                chars += len(p.extract_text() or "")
                if chars >= min_chars:
                    return True
        return False
    except Exception:
        return False


def run_ocrmypdf(src: Path, dst: Path, *, force: bool = False, timeout: int = 120, lang: Optional[str] = None) -> tuple[bool, str, str]:
    """Ejecuta ocrmypdf si está instalado. Devuelve (ok, stdout, stderr).

    - Si `force` es True, usa --force-ocr para forzar el rasterizado.
    - Si `force` es False, usa --skip-text para evitar OCR cuando ya hay texto.
    - Usa idioma de entorno IMPORT_OCR_LANG o spa+eng por defecto.
    """
    lang = lang or os.getenv("IMPORT_OCR_LANG", "spa+eng")
    args = [
        "ocrmypdf",
        "--language",
        lang,
        "--output-type",
        "pdf",
        "--rotate-pages",
        "--deskew",
    ]
    if force:
        args.append("--force-ocr")
    else:
        args.append("--skip-text")
    
    args += [str(src), str(dst)]
    
    try:
        r = subprocess.run(args, timeout=timeout, capture_output=True, text=True, encoding='utf-8', errors='replace')
        ok = r.returncode == 0 and dst.exists() and dst.stat().st_size > 0
        return ok, r.stdout, r.stderr
    except FileNotFoundError:
        return False, "", "ocrmypdf no está instalado o no se encuentra en el PATH."
    except Exception as e:
        return False, "", str(e)


def ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

