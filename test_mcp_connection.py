#!/usr/bin/env python
"""Script rápido para probar conectividad con MCP Web Search."""
import asyncio
from workers.discovery.source_finder import call_mcp_web_search

async def test():
    result = await call_mcp_web_search(
        query="carpa indoor 80x80 precio",
        max_results=5,
        user_role="admin"
    )
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        items = result.get("items", [])
        print(f"✅ Éxito! Encontrados {len(items)} resultados")
        for i, item in enumerate(items[:3], 1):
            print(f"\n{i}. {item.get('title', 'Sin título')}")
            print(f"   URL: {item.get('url', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(test())
