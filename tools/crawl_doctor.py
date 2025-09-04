"""Crawl Doctor: verifica dependencias y conectividad para el crawler de imágenes.

Uso:
  python -m tools.crawl_doctor

Chequea:
- Paquetes: requests, beautifulsoup4, httpx, pillow, tenacity, playwright (opcional)
- Playwright Chromium instalado
- Conectividad a https://www.santaplanta.com.ar (DNS/TLS)
- Acceso a robots.txt y a /shop/search/?q=test
- Muestra User-Agent efectivo y rate‑limit configurado por env
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path


def _check_pkg(name: str) -> dict:
    try:
        m = importlib.import_module(name)
        ver = getattr(m, "__version__", "unknown")
        return {"name": name, "ok": True, "version": ver}
    except Exception as e:
        return {"name": name, "ok": False, "error": str(e)}


def _check_playwright_browser() -> dict:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        return {"playwright": False, "chromium": False, "error": f"playwright import error: {e}"}
    # Try launching chromium briefly
    try:
        with sync_playwright() as p:  # type: ignore
            browser = p.chromium.launch(headless=True)
            browser.close()
        return {"playwright": True, "chromium": True}
    except Exception as e:  # likely needs install
        return {"playwright": True, "chromium": False, "error": f"chromium launch error: {e}", "hint": "Run: python -m playwright install chromium"}


def _check_connectivity() -> dict:
    try:
        import httpx
        base = os.getenv("CRAWL_PROVIDER_SANTAPLANTA_BASE", "https://www.santaplanta.com.ar")
        ua = os.getenv("CRAWL_USER_AGENT", "GrowenBot/1.0 (+contacto)")
        timeout = float(os.getenv("CRAWL_TIMEOUT", "20"))
        res = {"base": base, "ua": ua, "timeout": timeout}
        with httpx.Client(timeout=timeout, headers={"User-Agent": ua}) as c:
            r1 = c.get(base + "/robots.txt")
            res["robots"] = {"status": r1.status_code, "ok": r1.status_code == 200}
            r2 = c.get(base + "/shop/search/?q=test")
            res["search"] = {"status": r2.status_code, "ok": r2.status_code == 200, "len": len(r2.text)}
        return res
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    checks = {}
    checks["python"] = sys.version
    # Packages
    pkgs = [
        "requests",
        "beautifulsoup4",
        "httpx",
        "PIL.Image",
        "tenacity",
        "playwright",
    ]
    checks["packages"] = [_check_pkg(p) for p in pkgs]
    checks["playwright"] = _check_playwright_browser()
    checks["connectivity"] = _check_connectivity()
    checks["rate_limit"] = {
        "CRAWL_RATE_REQS_PER_SEC": float(os.getenv("CRAWL_RATE_REQS_PER_SEC", "1")),
        "CRAWL_BURST": int(os.getenv("CRAWL_BURST", "3")),
        "CRAWL_BACKOFF_BASE": float(os.getenv("CRAWL_BACKOFF_BASE", "1")),
        "CRAWL_RETRIES": int(os.getenv("CRAWL_RETRIES", "3")),
    }
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

