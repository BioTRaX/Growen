#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: main.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/main.py
# NG-HEADER: Descripción: FastAPI del servidor MCP de búsqueda web.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .tools import invoke_tool

app = FastAPI(title="MCP Web Search Server")


class InvokePayload(BaseModel):
    tool_name: str
    parameters: dict


@app.post("/invoke_tool")
async def _invoke(p: InvokePayload):
    try:
        res = await invoke_tool(p.tool_name, p.parameters)
        return {"tool_name": p.tool_name, "result": res}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="tool failure")


# Ejecutable local (opcional):
# uvicorn mcp_servers.web_search_server.main:app --host 0.0.0.0 --port 8002
