#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: normalize_ng_header.py
# NG-HEADER: Ubicación: tools/normalize_ng_header.py
# NG-HEADER: Descripción: Normaliza NG-HEADER (acentos y paths) en todo el repo
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, Tuple


ROOT = Path(__file__).resolve().parents[1]


LINE_STYLES = {
    'hash': lambda text: f"# NG-HEADER: {text}",
    'slash': lambda text: f"// NG-HEADER: {text}",
    'css': lambda text: f"/* NG-HEADER: {text} */",
    'html': lambda text: f"<!-- NG-HEADER: {text} -->",
}


def detect_style(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {'.py', '.sh', '.yml', '.yaml', '.cfg', '.toml'}:
        return 'hash'
    if ext in {'.ts', '.tsx', '.js', '.jsx'}:
        return 'slash'
    if ext in {'.css'}:
        return 'css'
    if ext in {'.html', '.htm', '.md'}:
        return 'html'
    # default to hash-style
    return 'hash'


def is_header_line(line: str) -> bool:
    # Accept any of the comment syntaxes and any mojibake for labels
    return bool(re.search(r"NG-HEADER\s*:\s*", line))


def split_shebang_and_text(text: str) -> Tuple[str, str]:
    if text.startswith('#!'):
        first_newline = text.find('\n')
        if first_newline != -1:
            return text[: first_newline + 1], text[first_newline + 1 :]
    return '', text


def normalize_header_block(path: Path, text: str) -> Tuple[str, bool]:
    nl = '\r\n' if '\r\n' in text else '\n'
    shebang, rest = split_shebang_and_text(text)
    lines = rest.splitlines()
    # Find existing header block start
    start = None
    for i, line in enumerate(lines[:20]):
        if is_header_line(line):
            start = i
            break
        if line.strip():
            # First non-empty non-header line, stop looking
            if i > 5:
                break
    if start is None:
        return text, False
    # Determine style from the first header line
    style = detect_style(path)
    # Collect header block lines
    end = start
    while end < len(lines) and is_header_line(lines[end]):
        end += 1

    header_lines = lines[start:end]
    # Extract existing description content (if any)
    desc_value = None
    for hl in header_lines:
        m = re.search(r"NG-HEADER\s*:\s*Descrip.*?:\s*(.*)$", hl, flags=re.IGNORECASE)
        if m:
            desc_value = m.group(1).strip()
            # Strip trailing comment tokens for CSS/HTML styles
            desc_value = re.sub(r"\s*\*\/\s*$", "", desc_value)
            desc_value = re.sub(r"\s*-->\s*$", "", desc_value)
            break
    if not desc_value:
        desc_value = "Pendiente de descripción"

    rel = path.relative_to(ROOT).as_posix()
    basename = path.name

    maker = LINE_STYLES[style]
    new_block = [
        maker(f"Nombre de archivo: {basename}"),
        maker(f"Ubicación: {rel}"),
        maker(f"Descripción: {desc_value}"),
        maker("Lineamientos: Ver AGENTS.md"),
    ]

    # Replace block
    new_lines = lines[:start] + new_block + lines[end:]
    new_text = shebang + (nl.join(new_lines) + (nl if text.endswith(('\n','\r','\r\n')) else ''))
    changed = new_text != text
    return new_text, changed


def iter_files() -> Iterable[Path]:
    skip_dirs = {'.git', '.venv', 'node_modules', 'dist', 'build', 'data', 'logs', '__pycache__'}
    for p in ROOT.rglob('*'):
        if p.is_dir():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        yield p


def has_ng_header(text: str) -> bool:
    # limit to first 200 lines for performance
    return 'NG-HEADER' in text[: 10000]


def load_text(path: Path) -> Tuple[str, str]:
    data = path.read_bytes()
    # Detect newline style
    # Decode: try utf-8 first, fallback latin-1 to preserve mojibake and then we will re-encode as utf-8
    try:
        txt = data.decode('utf-8')
    except UnicodeDecodeError:
        txt = data.decode('latin-1')
    return txt, ('\r\n' if b'\r\n' in data else '\n')


def main() -> None:
    ap = argparse.ArgumentParser(description='Normalize NG-HEADER blocks across repo')
    ap.add_argument('--check', action='store_true', help='Only report files that would change')
    ap.add_argument('--write', action='store_true', help='Write changes to files')
    args = ap.parse_args()

    to_fix: list[Path] = []
    changed_count = 0

    for path in iter_files():
        try:
            txt, _nl = load_text(path)
        except Exception:
            continue
        if not has_ng_header(txt):
            continue
        new_text, changed = normalize_header_block(path, txt)
        if changed:
            to_fix.append(path)
            if args.write:
                path.write_text(new_text, encoding='utf-8', newline='')
                changed_count += 1

    if args.check:
        for p in to_fix:
            print(p)
        print(f"Would change: {len(to_fix)} files")
    if args.write:
        print(f"Changed: {changed_count} files")


if __name__ == '__main__':
    main()
