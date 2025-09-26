# NG-HEADER: Nombre de archivo: seo.py
# NG-HEADER: Ubicación: services/media/seo.py
# NG-HEADER: Descripción: Utilidades de SEO para recursos multimedia.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional

from ai.router import AIRouter
from ai.types import Task
from agent_core.config import settings


def _truncate(text: str, max_len: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 1)].rstrip() + "…"


def gen_alt_title(product: dict, category: Optional[str] = None) -> dict:
    """Generate SEO-friendly ALT and Title in neutral Spanish.

    Inputs are plain dicts to avoid tight coupling with ORM models.
    """
    name = product.get("title") or product.get("name") or "Producto"
    brand = product.get("brand") or product.get("brand_name") or ""
    weight = product.get("weight")
    dims = product.get("dimensions")
    pieces: list[str] = [name]
    if brand:
        pieces.append(brand)
    if weight:
        pieces.append(str(weight))
    if dims:
        pieces.append(str(dims))
    if category:
        pieces.append(category)
    base = ", ".join([p for p in pieces if p])

    # Prompt AI, but keep deterministic fallback
    router = AIRouter(settings)
    prompt = (
        "Genera etiquetas ALT y Title concisas para una imagen de producto. "
        "Tono neutro, no de marketing. Español neutro. ALT <=120, Title <=60. "
        "No traduzcas marcas. Normaliza unidades. Devuelve JSON con campos 'alt' y 'title'.\n\n"
        f"Producto: {name}\nMarca: {brand}\nCategoria: {category or ''}\nEspecificaciones: peso={weight} dims={dims}"
    )
    try:
        text = router.run(Task.SEO.value, prompt)
        # Very simple parse: look for known keys
        alt = None
        title = None
        lower = text.lower()
        if "\"alt\"" in lower and "\"title\"" in lower:
            # naive extraction
            import re

            m_alt = re.search(r"\"alt\"\s*:\s*\"([^\"]+)\"", text)
            m_title = re.search(r"\"title\"\s*:\s*\"([^\"]+)\"", text)
            if m_alt:
                alt = m_alt.group(1)
            if m_title:
                title = m_title.group(1)
        if not alt:
            alt = base
        if not title:
            title = name if len(name) <= 60 else base
    except Exception:
        alt = base
        title = name

    return {"alt": _truncate(alt, 120), "title": _truncate(title, 60)}

