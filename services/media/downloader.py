# NG-HEADER: Nombre de archivo: downloader.py
# NG-HEADER: Ubicación: services/media/downloader.py
# NG-HEADER: Descripción: Descarga y persistencia de archivos multimedia.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

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
        # Rechazar credenciales embebidas y secuencias ambiguas.
        if p.username is not None or p.password is not None:
            return True
        bad = ["\\", "%00"]
        if any(b in url for b in bad):
            return True
        local_hosts = {"localhost", "0.0.0.0"}
        if host in local_hosts:
            return True
        return False
    except Exception:
        return True


def _allowed_host(host: str) -> bool:
    configured = {
        item.strip().lower().rstrip(".")
        for item in os.getenv("IMAGE_DOWNLOAD_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    normalized = host.lower().rstrip(".")
    return not configured or any(
        normalized == allowed or normalized.endswith(f".{allowed}")
        for allowed in configured
    )


def _is_public_unicast(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_private
    )


async def _validate_public_destination(url: str) -> set[str]:
    """Valida esquema, allowlist y todas las direcciones DNS antes de conectar."""

    if _suspicious(url):
        raise DownloadError("URL sospechosa o no permitida")
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".")
    if not _allowed_host(host):
        raise DownloadError("Dominio no permitido")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise DownloadError("No se pudo resolver el destino") from exc
    addresses = {str(ipaddress.ip_address(info[4][0])) for info in infos}
    if not addresses or any(not _is_public_unicast(ipaddress.ip_address(item)) for item in addresses):
        raise DownloadError("El destino resuelve a una red no pública")
    return addresses


def _validate_connected_peer(response: object, expected_ips: set[str]) -> None:
    """Comprueba el peer real para cerrar la ventana de DNS rebinding."""

    extensions = getattr(response, "extensions", {}) or {}
    network_stream = extensions.get("network_stream")
    peer = network_stream.get_extra_info("server_addr") if network_stream else None
    if not peer:
        raise DownloadError("No se pudo verificar la IP conectada")
    try:
        connected = str(ipaddress.ip_address(peer[0]))
    except (ValueError, TypeError, IndexError) as exc:
        raise DownloadError("Peer remoto inválido") from exc
    if not _is_public_unicast(ipaddress.ip_address(connected)) or connected not in expected_ips:
        raise DownloadError("El peer remoto no coincide con el DNS público validado")


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
    headers = {"User-Agent": DEFAULT_UA, "Accept": "image/*,*/*;q=0.8"}
    limits = httpx.Limits(max_connections=5, max_keepalive_connections=2)
    max_bytes = int(os.getenv("IMAGE_DOWNLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        follow_redirects=False,
        trust_env=False,
        headers=headers,
        limits=limits,
    ) as client:
        # Rate-limit global
        await get_limiter().acquire()
        current_url = url
        content = b""
        ctype = ""
        for redirect_count in range(4):
            expected_ips = await _validate_public_destination(current_url)
            async with client.stream("GET", current_url) as response:
                _validate_connected_peer(response, expected_ips)
                if response.is_redirect:
                    if redirect_count >= 3:
                        raise DownloadError("Demasiadas redirecciones")
                    location = response.headers.get("location")
                    if not location:
                        raise DownloadError("Redirección sin destino")
                    current_url = urljoin(current_url, location)
                    continue
                response.raise_for_status()
                ctype = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in {"image/jpeg", "image/png", "image/webp"}:
                    raise DownloadError(f"Tipo de contenido no permitido: {ctype or 'ausente'}")
                chunks: list[bytes] = []
                downloaded = 0
                async for chunk in response.aiter_bytes():
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise DownloadError("Archivo demasiado grande")
                    chunks.append(chunk)
                content = b"".join(chunks)
                break
        else:  # pragma: no cover - protegido por el límite explícito
            raise DownloadError("No se pudo completar la descarga")

    # Write under Productos/<product_id>/raw
    root = get_media_root()
    raw_dir = root / "Productos" / str(product_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = urlparse(current_url).path.split("/")[-1] or "image"
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
        source_url=current_url,
    )

