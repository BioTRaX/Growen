#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: stdio.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/stdio.py
# NG-HEADER: Descripción: Transporte STDIO local del MCP de SiYuan para Codex.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from .server import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
