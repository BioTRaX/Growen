# NG-HEADER: Nombre de archivo: downloader.py
# NG-HEADER: Ubicación: services/media/downloader.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from PIL import Image as PILImage

try:
    import clamd  # type: ignore
except Exception:  # pragma: no cover - optional import
    clamd = None  # type: ignore

# Nota: la librería clamd puede disparar un warning por uso de pkg_resources en runtime.
# Si se desea silenciarlo en tests sin ocultar otros DeprecationWarnings, añadir filtro fino en pytest.ini:
# filterwarnings =
#     ignore:.*pkg_resources.*:UserWarning:clamd

from . import get_media_root
from services.images.ratelimit import get_limiter


ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_UA = "GrowenBot/1.0 (+https://example.local)"


class DownloadError(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _suspicious(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ALLOWED_SCHEMES:
            return True
        if not p.netloc:
            return True
        host = p.hostname or ""
        # Simple denylist of suspicious patterns
        bad = ["@", "..", "\\", "%00"]
        if any(b in url for b in bad):
            return True
        # Disallow local addresses
        local_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
        if host in local_hosts:
            return True
        return False
    except Exception:
        return True


def _clamav_enabled() -> bool:
    return os.getenv("CLAMAV_ENABLED", "true").lower() == "true"


async def _clamav_scan(path: Path) -> None:
    if not _clamav_enabled():
        return
    if clamd is None:
        raise DownloadError("ClamAV requerido pero la libreria 'clamd' no esta disponible")
    host = os.getenv("CLAMD_HOST", "127.0.0.1")
    port = int(os.getenv("CLAMD_PORT", "3310"))
    cd = clamd.ClamdNetworkSocket(host=host, port=port)
    try:
        pong = cd.ping()
        if not pong:
            raise DownloadError("ClamAV no responde al ping")
    except Exception as e:
        raise DownloadError(f"ClamAV no disponible: {e}")
    res = cd.scan(str(path))
    # clamd returns { 'path': ('OK'|'FOUND', 'SIGNATURE') }
    try:
        status = list(res.values())[0][0]
    except Exception:
        raise DownloadError("ClamAV respuesta invalida")
    if status != "OK":
        raise DownloadError("Archivo infectado segun ClamAV")


@dataclass
class DownloadResult:
    path: Path
    sha256: str
    mime: Optional[str]
    size: int
    source_url: str


async def download_product_image(
    product_id: int,
    url: str,
    timeout: float = 30.0,
) -> DownloadResult:
    if _suspicious(url):
        raise DownloadError("URL sospechosa o no permitida")

    headers = {"User-Agent": DEFAULT_UA, "Accept": "image/*,*/*;q=0.8"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        # Rate-limit global
        await get_limiter().acquire()
        r = await client.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype not in {"image/jpeg", "image/png", "image/webp"}:
            # Some providers return octet-stream incorrectly; allow if bytes look like image
            if not ctype or ctype == "application/octet-stream":
                pass
            else:
                raise DownloadError(f"Tipo de contenido no permitido: {ctype}")
        content = r.content
        if len(content) > 10 * 1024 * 1024:
            raise DownloadError("Archivo demasiado grande (>10MB)")

    # Write under Productos/<product_id>/raw
    root = get_media_root()
    raw_dir = root / "Productos" / str(product_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = urlparse(url).path.split("/")[-1] or "image"
    # Sanitize
    name = name.replace("\\", "/").split("/")[-1]
    target = raw_dir / name
    i = 1
    while target.exists():
        stem = ".".join(name.split(".")[:-1]) or name
        ext = ("." + name.split(".")[-1]) if "." in name else ""
        target = raw_dir / f"{stem}-{i}{ext}"
        i += 1
    with open(target, "wb") as f:
        f.write(content)

    await _clamav_scan(target)
    # Validate dimensions
    min_side = int(os.getenv("IMAGE_MIN_SIZE", "600"))
    try:
        with PILImage.open(target) as im:
            w, h = im.size
        if w < min_side or h < min_side:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            raise DownloadError(f"Resolucion insuficiente (<{min_side}x{min_side})")
    except DownloadError:
        raise
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        raise DownloadError("Archivo de imagen invalido")
    return DownloadResult(
        path=target,
        sha256=_sha256(target),
        mime=ctype if ctype else None,
        size=target.stat().st_size,
        source_url=url,
    )

