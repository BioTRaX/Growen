from __future__ import annotations

"""Hybrid image crawler for Santa Planta.

Strategy:
- Search by title (requests+BS4) to collect product URLs (whitelist).
- For each URL: fetch HTML (requests). If no images or clear JS placeholders, try Playwright.
- Parse images from HTML (og:image, gallery <img>, JSON-LD Product.image).
- Pick primary + up to 2 seconds, filter thumbnails.

Provides a high-level `crawl_best_images(title)` that returns {primary, seconds} URLs.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import os
import re
import asyncio

import httpx
from bs4 import BeautifulSoup  # type: ignore
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type  # type: ignore
except Exception:  # pragma: no cover - optional
    # Provide no-op replacements so module can be imported in environments
    def retry(*a, **k):
        def _d(f):
            return f
        return _d

    def stop_after_attempt(n):
        return None

    def wait_exponential(*a, **k):
        return None

    def retry_if_exception_type(t):
        return None
from services.logging.ctx_logger import make_correlation_id, log_event_sync, save_snapshot_html, save_snapshot_image, log_event
from services.images.ratelimit import get_limiter


BASE = os.getenv("CRAWL_PROVIDER_SANTAPLANTA_BASE", "https://www.santaplanta.com.ar").rstrip("/")
UA = os.getenv("CRAWL_USER_AGENT", "GrowenBot/1.0 (+contacto)")
TIMEOUT = float(os.getenv("CRAWL_TIMEOUT", "20"))


def _good_img_url(u: str) -> bool:
    s = u.lower()
    if any(t in s for t in ("thumb", "mini", "small", "150x", "w=200", "w=300")):
        return False
    return True


def _abs(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return BASE + url
    return BASE + "/" + url


def _needs_js(html: str) -> bool:
    h = html.lower()
    return ("lazyload" in h or "data-src" in h) and ("<img" in h)


def _normalize_query(title: str) -> str:
    """Heurística simple para limpiar títulos ruidosos:
    - elimina paréntesis y su contenido
    - quita tokens promocionales (PACK, DESC, UND, LT, DM, etc) y porcentajes
    - elimina símbolos y colapsa espacios
    - limita a 3-5 primeras palabras
    - si la primera palabra es mayúscula corta (p. ej. marca), la descarta
    """
    t = title or ""
    # quita contenido entre paréntesis
    t = re.sub(r"\([^\)]*\)", " ", t)
    # elimina porcentajes y multiplicadores
    t = re.sub(r"\d+\s*[xX%]\s*\d*", " ", t)
    # elimina tokens promocionales/comunes
    t = re.sub(r"\b(PACK|DESC|DESCUENTO|UND|UNIDADES|U|LT|LTS|LITRO|DM|DM3|DM2|MINIMO|minimo)\b", " ", t, flags=re.IGNORECASE)
    # limpia símbolos
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    tokens = t.split()
    # descarta posible marca en mayúsculas al inicio
    if tokens and tokens[0].isupper() and 2 <= len(tokens[0]) <= 8:
        tokens = tokens[1:]
    # limita longitud
    if len(tokens) > 5:
        tokens = tokens[:5]
    # mínimo 2 tokens para evitar términos demasiado genéricos
    return " ".join(tokens)


@retry(stop=stop_after_attempt(int(os.getenv("CRAWL_RETRIES", "3"))), wait=wait_exponential(multiplier=float(os.getenv("CRAWL_BACKOFF_BASE", "1")), min=1, max=15), reraise=True)
def _http_get(url: str) -> httpx.Response:
    # Sync rate limit for sync code paths
    get_limiter().acquire_sync()
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": UA}, follow_redirects=True) as c:
        r = c.get(url)
        if r.status_code >= 500 or r.status_code in (408, 429):
            # trigger retry
            raise httpx.HTTPError(f"status {r.status_code}")
        return r


async def search_pages_santaplanta(title: str, max_results: int = 5, correlation_id: str | None = None, db=None) -> List[str]:
    correlation = correlation_id or make_correlation_id()
    log_event_sync(correlation, None, None, "search", message="search_start", title=title)
    # Queries: normalized, short, y fallback por subfrases
    norm = _normalize_query(title)
    candidates_q: List[str] = []
    if norm:
        candidates_q.append(norm)
        parts = norm.split()
        if len(parts) >= 3:
            candidates_q.append(" ".join(parts[:3]))
        if len(parts) >= 2:
            candidates_q.append(" ".join(parts[:2]))
    # Último intento: primeras 2 palabras del título original (sin paréntesis)
    if not candidates_q:
        base = re.sub(r"\([^\)]*\)", " ", title or "").strip()
        tokens = base.split()
        if tokens:
            candidates_q.append(" ".join(tokens[:2]))

    out: List[str] = []
    for qi in candidates_q:
        try:
            q = qi.strip().replace(" ", "+")
            url = f"{BASE}/shop/search/?q={q}"
            r = _http_get(url)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = str(a["href"]) or ""
                if href.startswith("/shop/products/") or href.startswith("/shop/catalog"):
                    if href.startswith("/shop/products/"):
                        u = _abs(href)
                        if u not in out:
                            out.append(u)
                if len(out) >= max_results:
                    break
            if out:
                break
        except Exception:
            continue
    # attempt DB log as well
    try:
        await log_event(db, level="INFO", correlation_id=correlation, product_id=None, step="search:done", urls=out[:max_results], query_used=(candidates_q[0] if candidates_q else None))
    except Exception:
        pass
    log_event_sync(correlation, None, None, "search", message="search_done", title=title, urls=out[:max_results])
    return out


def parse_images_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    imgs: List[str] = []
    # meta og:image
    for m in soup.find_all("meta", attrs={"property": "og:image"}):
        c = m.get("content") or ""
        if c and _good_img_url(c):
            imgs.append(_abs(c))
    # gallery imgs
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            # srcset fallback: pick last candidate
            srcset = img.get("srcset") or ""
            if srcset:
                try:
                    last = srcset.split(",")[-1].strip().split(" ")[0]
                    src = last
                except Exception:
                    src = ""
        if src and _good_img_url(src):
            imgs.append(_abs(src))
    # JSON-LD Product.image
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            import json

            data = json.loads(script.text)
            if isinstance(data, dict) and "image" in data:
                val = data["image"]
                if isinstance(val, str) and _good_img_url(val):
                    imgs.append(_abs(val))
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, str) and _good_img_url(v):
                            imgs.append(_abs(v))
        except Exception:
            pass
    # Dedupe preserving order
    seen: set[str] = set()
    out: List[str] = []
    for u in imgs:
        if u not in seen:
            seen.add(u)
            out.append(u)
    # If none found, caller may save snapshot
    return out


async def fetch_with_playwright(url: str, correlation_id: str | None = None, db=None) -> Tuple[str, List[str], str | None]:
    """Return a 3-tuple (html, image_urls, screenshot_path) using Playwright if available; otherwise empty values."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        # Playwright not installed or failed to import
        return "", [], None
    html = ""
    imgs: List[str] = []
    screenshot_path: Optional[str] = None
    try:
        def run() -> Tuple[str, List[str], Optional[str]]:
            with sync_playwright() as p:  # type: ignore
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=UA)
                page.set_default_timeout(TIMEOUT * 1000)
                page.goto(url)
                page.wait_for_selector("img")
                # scroll to lazy-load
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                html = page.content()
                # take screenshot bytes
                try:
                    buf = page.screenshot(full_page=True)
                except Exception:
                    buf = None
                urls = []
                for el in page.query_selector_all("img"):
                    src = el.get_attribute("src") or el.get_attribute("data-src") or ""
                    if src and _good_img_url(src):
                        urls.append(_abs(src))
                browser.close()
                if buf:
                    # save screenshot bytes
                    try:
                        sp = save_snapshot_image(correlation_id or make_correlation_id(), url.split("/")[-1][:60], buf, ext="png")
                        screenshot: Optional[str] = sp
                    except Exception:
                        screenshot = None
                else:
                    screenshot = None
                return html, urls, screenshot

        import concurrent.futures

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            html, imgs, screenshot_path = await loop.run_in_executor(pool, run)
    except Exception:
        return "", [], None
    return html, imgs, screenshot_path


def pick_primary_and_seconds(urls: List[str]) -> Dict[str, Any]:
    if not urls:
        return {"primary": None, "seconds": []}
    # naive: prefer largest-ish by filename hints (e.g., -800, -1200, w=1600)
    def score(u: str) -> int:
        m = re.search(r"(\d{3,4})(?:x\d{3,4})?", u)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return 0
        m2 = re.search(r"w=(\d{3,4})", u)
        return int(m2.group(1)) if m2 else 0

    ordered = sorted(urls, key=score, reverse=True)
    primary = ordered[0]
    seconds = [u for u in ordered[1:] if _good_img_url(u)]
    seconds = seconds[:2]
    return {"primary": primary, "seconds": seconds}


async def crawl_best_images(title: str, correlation_id: str | None = None, db=None) -> Dict[str, Any]:
    correlation = correlation_id or make_correlation_id()
    log_event_sync(correlation, None, None, "crawl", message="crawl_start", title=title)
    try:
        await log_event(db, level="INFO", correlation_id=correlation, product_id=None, step="crawl:start", title=title)
    except Exception:
        pass
    urls = await search_pages_santaplanta(title, correlation_id=correlation, db=db)
    all_imgs: List[str] = []
    for u in urls:
        log_event_sync(correlation, None, None, "open", message="open_start", url=u)
        r = _http_get(u)
        imgs = parse_images_from_html(r.text)
        if not imgs or _needs_js(r.text):
            html2, js_imgs, screenshot_path = await fetch_with_playwright(u, correlation_id=correlation, db=db)
            if js_imgs:
                imgs = js_imgs
            # Save snapshot when no images
            if not imgs:
                p = save_snapshot_html(correlation, u.split("/")[-1][:60], html2 or r.text)
                log_event_sync(correlation, None, None, "parse", message="no_images_snapshot", url=u, snapshot=p, screenshot=screenshot_path)
        if imgs:
            log_event_sync(correlation, None, None, "parse", message="images_found", url=u, images_found=len(imgs))
            all_imgs.extend(imgs)
            break
    # dedupe
    seen: set[str] = set()
    clean: List[str] = []
    for i in all_imgs:
        if i not in seen:
            seen.add(i)
            clean.append(i)
    picks = pick_primary_and_seconds(clean)
    try:
        await log_event(db, level="INFO", correlation_id=correlation, product_id=None, step="pick:done", picks=picks)
    except Exception:
        pass
    log_event_sync(correlation, None, None, "pick", message="pick_done", title=title, picks=picks)
    log_event_sync(correlation, None, None, "crawl", message="crawl_done", title=title, images_found=len(clean))
    try:
        await log_event(db, level="INFO", correlation_id=correlation, product_id=None, step="crawl:done", images_found=len(clean))
    except Exception:
        pass
    return picks
