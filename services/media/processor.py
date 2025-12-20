# NG-HEADER: Nombre de archivo: processor.py
# NG-HEADER: Ubicación: services/media/processor.py
# NG-HEADER: Descripción: Procesamiento y conversión de archivos multimedia.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from PIL import Image, ImageOps, ImageEnhance

# Registrar soporte para HEIF/HEIC si pillow-heif está instalado
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    # pillow-heif no está instalado, HEIF/HEIC no se podrán procesar
    pass

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


def rotate_image(source: Path, degrees: int, dest_dir: Path | None = None) -> Path:
    """Rota una imagen en 90, 180 o 270 grados.
    
    Args:
        source: Ruta del archivo fuente
        degrees: Grados de rotación (90, 180, 270 o -90, -180, -270)
        dest_dir: Directorio destino opcional
    
    Returns:
        Path al archivo rotado
    """
    # Normalizar grados
    degrees = degrees % 360
    if degrees not in (90, 180, 270):
        raise ValueError("Solo se permiten rotaciones de 90, 180 o 270 grados")
    
    with Image.open(source) as im:
        # Pillow rota en sentido antihorario, así que invertimos
        rotated = im.rotate(-degrees, expand=True)
        
        if dest_dir is None:
            out_path = source.parent / f"{source.stem}-rot{degrees}{source.suffix}"
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            out_path = dest_dir / f"{source.stem}-rot{degrees}{source.suffix}"
        
        # Mantener formato original
        rotated.save(out_path)
        return out_path


def crop_square(source: Path, dest_dir: Path | None = None) -> Path:
    """Recorta una imagen a cuadrado centrado.
    
    Toma el centro de la imagen y genera un cuadrado del tamaño
    del lado menor.
    
    Args:
        source: Ruta del archivo fuente  
        dest_dir: Directorio destino opcional
    
    Returns:
        Path al archivo recortado
    """
    with Image.open(source) as im:
        w, h = im.size
        size = min(w, h)
        
        # Calcular coordenadas del crop centrado
        left = (w - size) // 2
        top = (h - size) // 2
        right = left + size
        bottom = top + size
        
        cropped = im.crop((left, top, right, bottom))
        
        if dest_dir is None:
            out_path = source.parent / f"{source.stem}-sq{source.suffix}"
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            out_path = dest_dir / f"{source.stem}-sq{source.suffix}"
        
        cropped.save(out_path)
        return out_path


def apply_logo(
    img_path: Path,
    logo_path: Path,
    position: str = "br",
    scale_percent: float = 20.0,
    opacity: float = 0.9,
    margin_percent: float = 2.0,
    in_place: bool = True,
) -> Path:
    """Aplica un logo PNG transparente sobre una imagen.
    
    Args:
        img_path: Ruta de la imagen base
        logo_path: Ruta del logo PNG con transparencia
        position: Posición del logo (tl, tr, bl, br, center)
        scale_percent: Tamaño del logo como porcentaje del ancho de imagen (1-50)
        opacity: Opacidad del logo (0.0-1.0)
        margin_percent: Margen desde el borde como porcentaje
        in_place: Si es True, sobrescribe la imagen original
    
    Returns:
        Path al archivo con logo aplicado
    """
    with Image.open(img_path) as base_original:
        # Keep original mode for final save
        original_mode = base_original.mode
        
        # Work in RGBA for compositing
        base = base_original.convert("RGBA")
        
        with Image.open(logo_path) as logo:
            logo = logo.convert("RGBA")
            
            # Scale logo to specified percentage of image width
            scale_percent = max(1.0, min(50.0, scale_percent))
            target_width = int(base.width * (scale_percent / 100.0))
            if target_width < 10:
                target_width = 10
            ratio = target_width / logo.width
            new_height = int(logo.height * ratio)
            if new_height < 1:
                new_height = 1
            logo = logo.resize((target_width, new_height), Image.Resampling.LANCZOS)
            
            # Apply opacity
            if opacity < 1.0:
                alpha = logo.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(max(0.0, min(1.0, opacity)))
                logo.putalpha(alpha)
            
            # Calculate position
            margin = int(base.width * (margin_percent / 100.0))
            
            if position == "tl":
                x, y = margin, margin
            elif position == "tr":
                x, y = base.width - logo.width - margin, margin
            elif position == "bl":
                x, y = margin, base.height - logo.height - margin
            elif position == "center":
                x = (base.width - logo.width) // 2
                y = (base.height - logo.height) // 2
            else:  # br (default)
                x, y = base.width - logo.width - margin, base.height - logo.height - margin
            
            # Paste logo with its alpha channel as mask (preserves transparency)
            base.paste(logo, (x, y), logo)
        
        # Determine output path
        if in_place:
            # Save over original (convert to RGB if source wasn't RGBA)
            out_path = img_path
            # Detect original format (default to JPEG if no extension)
            suffix = (img_path.suffix or "").lower()
            if suffix in ('.jpg', '.jpeg'):
                base.convert("RGB").save(out_path, format="JPEG", quality=95)
            elif suffix == '.png':
                base.save(out_path, format="PNG")
            elif suffix == '.webp':
                base.save(out_path, format="WEBP", quality=90)
            else:
                # No extension or unknown - default to JPEG
                base.convert("RGB").save(out_path, format="JPEG", quality=95)
        else:
            out_path = img_path.parent / f"{img_path.stem}-logo{img_path.suffix or '.jpg'}"
            base.convert("RGB").save(out_path, format="JPEG", quality=95)
        
        return out_path
