#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: invoke_siyuan_task_database.py
# NG-HEADER: Ubicación: scripts/invoke_siyuan_task_database.py
# NG-HEADER: Descripción: Invoca por MCP STDIO la creación segura de una base de tareas privada.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def invoke(document_id: str) -> dict[str, object]:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.siyuan_server.stdio"],
        cwd=ROOT,
    )
    async with stdio_client(server) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            catalog = await session.list_tools()
            if "create_siyuan_task_database" not in {tool.name for tool in catalog.tools}:
                raise RuntimeError("siyuan_task_database_tool_unavailable")
            result = await session.call_tool(
                "create_siyuan_task_database",
                {"document_id": document_id},
            )
            if result.isError:
                raise RuntimeError("siyuan_task_database_tool_failed")
            if not isinstance(result.structuredContent, dict):
                raise RuntimeError("siyuan_task_database_response_invalid")
            return result.structuredContent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crea por MCP STDIO una base de tareas en un documento privado de SiYuan."
    )
    parser.add_argument("document_id")
    result = asyncio.run(invoke(parser.parse_args().document_id))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
