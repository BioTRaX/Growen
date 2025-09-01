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


def get_media_root() -> Path:
    from pathlib import Path
    import os
    ROOT = Path(__file__).resolve().parents[2]
    return Path(os.getenv("MEDIA_ROOT", str(ROOT / "Devs" / "Imagenes")))


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def save_upload(category: str, filename: str, file: UploadFile) -> tuple[Path, str]:
    """Save an UploadFile under category or category/YYYY/MM and return (path, sha256).

    If ``category`` contains path separators (``/`` or ``\\``), it is treated as a nested path
    relative to MEDIA_ROOT and no year/month subfolders are added.
    """
    from datetime import datetime
    root = get_media_root()
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
