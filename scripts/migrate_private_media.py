#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: migrate_private_media.py
# NG-HEADER: Ubicación: scripts/migrate_private_media.py
# NG-HEADER: Descripción: Copia y verifica media privada fuera del árbol público sin eliminar originales.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Migración idempotente de media privada de ventas, compras y conocimiento."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


PRIVATE_PREFIXES = (Path("sales"), Path("canonical-knowledge"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate_media(
    public_root: Path,
    private_root: Path,
    *,
    apply: bool,
    purchases_root: Path | None = None,
) -> dict:
    """Copia contenido privado, verifica hashes y conserva siempre el origen."""

    public_root = public_root.resolve()
    private_root = private_root.resolve()
    if public_root == private_root:
        raise ValueError("public_and_private_media_roots_must_differ")

    sources = [(public_root / prefix, prefix) for prefix in PRIVATE_PREFIXES]
    if purchases_root is not None:
        sources.append((purchases_root.resolve(), Path("purchases")))

    entries: list[dict] = []
    for source_dir, target_prefix in sources:
        if not source_dir.exists():
            continue
        for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            relative = target_prefix / source.relative_to(source_dir)
            target = private_root / relative
            source_hash = _sha256(source)
            status = "would_copy"
            if target.exists():
                if _sha256(target) != source_hash:
                    raise RuntimeError(f"destination_hash_conflict:{relative.as_posix()}")
                status = "verified_existing"
            elif apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(f".{target.name}.migrating")
                shutil.copy2(source, temporary)
                if _sha256(temporary) != source_hash:
                    temporary.unlink(missing_ok=True)
                    raise RuntimeError(f"copied_hash_mismatch:{relative.as_posix()}")
                os.replace(temporary, target)
                status = "copied_verified"
            entries.append(
                {
                    "path": relative.as_posix(),
                    "sha256": source_hash,
                    "status": status,
                    "source_preserved": source.exists(),
                }
            )
    return {"mode": "apply" if apply else "dry-run", "files": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Sólo informa; modo predeterminado")
    mode.add_argument("--apply", action="store_true", help="Copia y verifica, sin borrar originales")
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument(
        "--purchases-root",
        type=Path,
        default=Path("data/purchases"),
        help="Raíz legacy de compras que se copiará a PRIVATE_MEDIA_ROOT/purchases",
    )
    args = parser.parse_args()
    manifest = migrate_media(
        args.public_root,
        args.private_root,
        apply=args.apply,
        purchases_root=args.purchases_root,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
