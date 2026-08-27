<!-- NG-HEADER: Nombre de archivo: README.md -->
<!-- NG-HEADER: Ubicación: mcp_servers/siyuan_server/README.md -->
<!-- NG-HEADER: Descripción: Operación y contratos del MCP documental de SiYuan. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# MCP SiYuan

Integra el notebook `Nice Grow` mediante la API local de SiYuan. Codex usa STDIO y los consumidores HTTP usan `http://127.0.0.1:8104/mcp` con JWT de Growen.

## Tools

- `list_siyuan_notebooks`: lectura.
- `search_siyuan_docs`: búsqueda SQL fija y `readonly`.
- `read_siyuan_document`: exportación Markdown.
- `create_siyuan_document`: creación sin sobrescritura bajo `/Growen`.

## Inicio

```powershell
.\scripts\setup-siyuan.ps1 -StartHttpMcp
.\scripts\start-dev.ps1 -WithSiyuanMcp
```

El token se lee desde `SIYUAN_API_TOKEN_FILE`; no debe copiarse al repositorio ni mostrarse en logs.

