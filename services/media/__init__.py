# NG-HEADER: Nombre de archivo: __init__.py
# NG-HEADER: Ubicación: services/media/__init__.py
# NG-HEADER: Descripción: Inicializa servicios de gestión de media.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Media helpers: paths, naming, and simple file ops."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import UploadFile


@dataclass
class MediaConfig:
    root: Path
    base_url: str = "/media"


def get_public_media_root() -> Path:
    """Raíz montada en ``/media`` para imágenes comerciales publicables."""

    project_root = Path(__file__).resolve().parents[2]
    configured = os.getenv("PUBLIC_MEDIA_ROOT") or os.getenv("MEDIA_ROOT")
    return Path(configured) if configured else project_root / "Devs" / "Imagenes"


def get_private_media_root() -> Path:
    """Raíz no montada como estática para documentos transaccionales."""

    project_root = Path(__file__).resolve().parents[2]
    configured = os.getenv("PRIVATE_MEDIA_ROOT")
    return Path(configured) if configured else project_root / "Devs" / "PrivateMedia"


def get_media_root() -> Path:
    """Alias compatible para consumidores históricos de imágenes públicas."""

    return get_public_media_root()


def resolve_private_media_path(relative_path: str) -> Path:
    """Resuelve una ruta persistida sin permitir escapes del árbol privado."""

    root = get_private_media_root().resolve()
    candidate = (root / relative_path).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("private_media_path_outside_root")
    return candidate


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def _save_upload_to(
    root: Path,
    category: str,
    filename: str,
    file: UploadFile,
) -> tuple[Path, str]:
    """Save an UploadFile under category or category/YYYY/MM and return (path, sha256).

    If ``category`` contains path separators (``/`` or ``\\``), it is treated as a nested path
    relative to MEDIA_ROOT and no year/month subfolders are added.
    """
    from datetime import datetime
    now = datetime.utcnow()
    # If category looks like a nested path, do not add date subfolders
    if ("/" in category) or ("\\" in category):
        dir_ = root / Path(category)
    else:
        dir_ = root / category / f"{now.year:04d}" / f"{now.month:02d}"
    dir_.mkdir(parents=True, exist_ok=True)

    safe = filename.replace("\\", "/").split("/")[-1]
    target = dir_ / safe
    i = 1
    while target.exists():
        stem = "".join(safe.split(".")[:-1]) or safe
        ext = ("." + safe.split(".")[-1]) if "." in safe else ""
        target = dir_ / f"{stem}-{i}{ext}"
        i += 1

    with open(target, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return target, sha256_of_file(target)


async def save_upload(category: str, filename: str, file: UploadFile) -> tuple[Path, str]:
    """Guarda contenido publicable bajo ``PUBLIC_MEDIA_ROOT``."""

    return await _save_upload_to(get_public_media_root(), category, filename, file)


async def save_private_upload(
    category: str,
    filename: str,
    file: UploadFile,
) -> tuple[Path, str]:
    """Guarda contenido privado fuera del árbol servido por ``/media``."""

    return await _save_upload_to(get_private_media_root(), category, filename, file)
