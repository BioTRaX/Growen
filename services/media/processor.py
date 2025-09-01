# NG-HEADER: Nombre de archivo: processor.py
# NG-HEADER: Ubicación: services/media/processor.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from PIL import Image, ImageOps, ImageEnhance

try:
    from rembg import remove as rembg_remove  # type: ignore
except Exception:  # pragma: no cover - optional import
    rembg_remove = None  # type: ignore

from . import get_media_root


DerivKind = Literal["thumb", "card", "full"]


def _ensure_webp(img: Image.Image) -> Image.Image:
    if img.mode not in ("RGB", "RGBA"):
        return img.convert("RGBA" if "A" in img.getbands() else "RGB")
    return img


def _square_pad(img: Image.Image, size: int, color=(255, 255, 255, 0)) -> Image.Image:
    # Keep aspect ratio, fit within size, pad to square
    img = ImageOps.contain(img, (size, size))
    bg = Image.new("RGBA", (size, size), color)
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    bg.paste(img, (x, y), img if img.mode == "RGBA" else None)
    return bg


def _save_webp(path: Path, img: Image.Image, quality: int = 80) -> None:
    img.save(path, format="WEBP", quality=quality, method=6)


@dataclass
class ProcessedPaths:
    thumb: Path
    card: Path
    full: Path


def to_square_webp_set(
    source: Path,
    dest_dir: Path,
    base_name: str,
    quality: int = 80,
) -> ProcessedPaths:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        im = _ensure_webp(im)
        sizes = {"thumb": 256, "card": 800, "full": 1600}
        out: dict[str, Path] = {}
        for kind, px in sizes.items():
            sq = _square_pad(im, px)
            out_path = dest_dir / f"{base_name}-{kind}.webp"
            _save_webp(out_path, sq, quality=quality)
            out[kind] = out_path
    return ProcessedPaths(thumb=out["thumb"], card=out["card"], full=out["full"])  # type: ignore


def apply_watermark(img_path: Path, logo_path: Path, pos: str = "br", opacity: float = 0.18, dest_dir: Path | None = None) -> Path:
    with Image.open(img_path) as base:
        base = base.convert("RGBA")
        with Image.open(logo_path) as logo:
            logo = logo.convert("RGBA")
            # Scale logo to 20% of image width
            scale = max(1, int(base.width * 0.2))
            ratio = scale / logo.width
            logo = logo.resize((scale, int(logo.height * ratio)))
            # Apply opacity
            alpha = logo.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(max(0.0, min(1.0, opacity)))
            logo.putalpha(alpha)
            # Position
            margin = int(base.width * 0.02)
            if pos == "tl":
                x, y = margin, margin
            elif pos == "tr":
                x, y = base.width - logo.width - margin, margin
            elif pos == "bl":
                x, y = margin, base.height - logo.height - margin
            else:  # br
                x, y = base.width - logo.width - margin, base.height - logo.height - margin
            base.alpha_composite(logo, (x, y))
        if dest_dir is None:
            out = img_path.with_suffix("")
            out = out.parent / (out.name + "-wm.webp")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            out = dest_dir / (img_path.stem + "-wm.webp")
        _save_webp(out, base.convert("RGBA"))
        return out


def remove_bg(source: Path, dest_dir: Path | None = None) -> Path:
    if rembg_remove is None:
        raise RuntimeError("rembg no disponible")
    with Image.open(source) as im:
        out = rembg_remove(im)
        if dest_dir is None:
            out_path = source.with_suffix("")
            out_path = out_path.parent / (out_path.name + "-nobg.png")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            out_path = dest_dir / (source.stem + "-nobg.png")
        out.save(out_path)
        return out_path
