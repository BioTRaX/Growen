# NG-HEADER: Nombre de archivo: santaplanta.py
# NG-HEADER: Ubicación: services/scrapers/santaplanta.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup  # type: ignore


BASE = "https://www.santaplanta.com.ar"
WHITELIST_PATH_PREFIX = ("/shop/products/", "/shop/catalog")


@dataclass
class FoundImage:
    url: str
    width: Optional[int]
    height: Optional[int]


def _is_whitelisted(url: str) -> bool:
    try:
        p = urlparse(url)
        return any(p.path.startswith(pref) for pref in WHITELIST_PATH_PREFIX)
    except Exception:
        return False


def _good_image(src: str) -> bool:
    s = src.lower()
    if any(tag in s for tag in ("-thumb", "-mini", "thumbnail")):
        return False
    return True


from services.images.ratelimit import get_limiter


async def _get(client: httpx.AsyncClient, url: str) -> str:
    # Global rate-limit + small jitter
    await get_limiter().acquire()
    await asyncio.sleep(0.15 + random.random() * 0.25)
    r = await client.get(url)
    r.raise_for_status()
    return r.text


async def search_by_title(title: str, max_results: int = 3) -> List[str]:
    q = title.strip().replace(" ", "+")
    url = f"{BASE}/shop/search/?q={q}"
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "GrowenBot/1.0"}) as client:
        html = await _get(client, url)
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            absu = urljoin(BASE, href)
            if _is_whitelisted(absu) and absu not in urls:
                urls.append(absu)
            if len(urls) >= max_results:
                break
        return urls


async def extract_product_image(prod_url: str) -> Optional[str]:
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "GrowenBot/1.0"}) as client:
        html = await _get(client, prod_url)
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[FoundImage] = []
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if not src:
                continue
            if not _good_image(src):
                continue
            w = None
            h = None
            try:
                w = int(img.get("width") or 0) or None
                h = int(img.get("height") or 0) or None
            except Exception:
                pass
            candidates.append(FoundImage(url=urljoin(BASE, src), width=w, height=h))
        # heaviest first by width
        candidates.sort(key=lambda c: c.width or 0, reverse=True)
        for c in candidates:
            if (c.width or 0) >= 400:
                return c.url
        return candidates[0].url if candidates else None


async def crawl_catalog(max_pages: int = 5) -> list[str]:
    """Traverse known catalog pages and categories collecting product URLs.

    Whitelists only /shop/catalog* and /shop/products/*
    """
    seen: set[str] = set()
    out: list[str] = []
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "GrowenBot/1.0"}) as client:
        to_visit = [f"{BASE}/shop/catalog"]
        pages = 0
        while to_visit and pages < max_pages:
            url = to_visit.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                html = await _get(client, url)
            except Exception:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # collect product and catalog links
            for a in soup.find_all("a", href=True):
                href = urljoin(BASE, a["href"])
                if not _is_whitelisted(href):
                    continue
                if href.startswith(f"{BASE}/shop/products/"):
                    if href not in out:
                        out.append(href)
                elif href.startswith(f"{BASE}/shop/catalog") and href not in seen:
                    to_visit.append(href)
            pages += 1
    return out
