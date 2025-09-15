#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: merge_heads_and_stamp.py
# NG-HEADER: Ubicación: scripts/merge_heads_and_stamp.py
# NG-HEADER: Descripción: Unifica múltiples heads de Alembic creando/stampeando un merge ya existente
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Herramienta para consolidar múltiples heads de Alembic.

Uso:
    python scripts/merge_heads_and_stamp.py --target 20250913_merge_heads

Pasos que realiza:
 1. Detecta heads actuales (`alembic heads`).
 2. Verifica que el target merge exista como archivo en `db/migrations/versions`.
 3. Conecta a la base y lee filas de `alembic_version`.
 4. Si hay más de una fila y el merge file existe, reemplaza todas por la versión merge.
 5. Imprime resumen y recomendaciones.

NOTA: No genera automáticamente el archivo de merge; debe existir.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT / 'db' / 'migrations' / 'versions'
ALEMBIC = [sys.executable, '-m', 'alembic', '-c', str(ROOT / 'alembic.ini')]


def sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"Comando {' '.join(cmd)} falló:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True, help='Revision ID del merge que quedará como único head')
    args = ap.parse_args()

    load_dotenv(ROOT / '.env')
    url = os.getenv('DB_URL')
    if not url:
        print('DB_URL no definido en entorno/.env', file=sys.stderr)
        return 1

    # 1. Heads actuales
    heads_out = sh(ALEMBIC + ['heads'])
    heads = [l.strip().split()[0] for l in heads_out.splitlines() if l.strip()]
    print('Heads detectados:', heads)

    # 2. Verificar archivo target
    merge_file = None
    for p in VERSIONS_DIR.glob('*.py'):
        if args.target in p.read_text(encoding='utf-8'):
            merge_file = p
            break
    if not merge_file:
        print(f'No se encontró archivo de migración que contenga {args.target}', file=sys.stderr)
        return 1
    print('Archivo merge localizado:', merge_file.name)

    # 3. Leer filas actuales
    engine = create_engine(url, future=True)
    with engine.begin() as conn:
        revs = conn.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        print('Filas actuales alembic_version:', revs)
        if revs == [args.target]:
            print('Ya está consolidado. Nada que hacer.')
            return 0
        if len(revs) == 1 and revs[0] != args.target:
            # Simplemente actualizar
            conn.execute(text('UPDATE alembic_version SET version_num=:v'), {'v': args.target})
            print('Actualizada versión única a target.')
            return 0
        # 4. Multiples filas -> consolidar
        if len(revs) > 1:
            print('Consolidando múltiples filas en alembic_version ->', args.target)
            conn.execute(text('DELETE FROM alembic_version'))
            conn.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'), {'v': args.target})
            print('Consolidación realizada.')
    # 5. Mostrar current
    current = sh(ALEMBIC + ['current'])
    print('alembic current tras consolidación:\n', current)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
