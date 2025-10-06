<!-- NG-HEADER: Nombre de archivo: README.md -->
<!-- NG-HEADER: Ubicación: mcp_servers/products_server/README.md -->
<!-- NG-HEADER: Descripción: Documentación del servidor MCP de productos (MVP) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Servidor MCP de Productos (MVP)

Este microservicio expone herramientas ("tools") para que un agente de IA (LLM) acceda de forma segura y estandarizada a información de productos del sistema Growen. Implementa el **Model Context Protocol (MCP)** de manera simplificada: un único endpoint HTTP que recibe el nombre de la herramienta y parámetros.

## Objetivos (MVP)
- No accede directamente a la base de datos; actúa como cliente HTTP de la API principal (`api` en la red Docker).
- Control de acceso básico por rol (`user_role`).
- Diseño extensible para añadir niveles de detalle futuros (segundo nivel, extendido) sin reescrituras grandes.

## Endpoints

| Método | Ruta         | Descripción |
|--------|--------------|-------------|
| POST   | `/invoke_tool` | Invoca una herramienta registrada |
| GET    | `/health`       | Chequeo de salud simple |

### Ejemplo de petición
```bash
curl -X POST http://localhost:8100/invoke_tool \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"get_product_info","parameters":{"sku":"ABC123","user_role":"viewer"}}'
```

### Respuesta típica
```json
{
  "tool_name": "get_product_info",
  "result": {
    "sku": "ABC123",
    "name": "Producto Demo",
    "sale_price": 199.9,
    "stock": 42
  }
}
```

## Tools implementadas

1. `get_product_info`
   - Accesible para cualquier rol.
   - Retorna: `sku, name, sale_price, stock`.
2. `get_product_full_info`
   - Requiere rol en {`admin`, `colaborador`}.
   - En este MVP retorna lo mismo que la anterior. Se ampliará con detalles adicionales.

## Roles y permisos (MVP)
| Rol | get_product_info | get_product_full_info |
|-----|------------------|-----------------------|
| admin | ✅ | ✅ |
| colaborador | ✅ | ✅ |
| viewer / otros | ✅ | ❌ (403) |

## Estructura
```
mcp_servers/
  products_server/
    main.py          # FastAPI app y endpoint /invoke_tool
    tools.py         # Implementación de tools y dispatcher
    Dockerfile       # Imagen independiente
    requirements.txt # Dependencias del microservicio
    tests/           # Pruebas unitarias y de integración (esqueleto)
```

## Ejecución local (sin Docker)
```bash
uvicorn mcp_servers.products_server.main:app --reload --port 8100
```

## Docker
Agregado al `docker-compose.yml` como servicio `mcp_products`.

Build manual:
```bash
docker build -t growen-mcp-products -f mcp_servers/products_server/Dockerfile .
```
Run manual:
```bash
docker run --rm -p 8100:8100 --name mcp_products growen-mcp-products
```

## Dependencias nuevas
Listado en `mcp_servers/products_server/requirements.txt` (fastapi, uvicorn, httpx, pydantic). No afectan `requirements.txt` raíz.

## Variables de entorno soportadas (MVP ampliado)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `API_BASE_URL` | URL base de la API principal consumida vía HTTP | `http://api:8000` |
| `LOG_LEVEL` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`, etc.) | `info` |
| `MCP_CACHE_TTL_SECONDS` | TTL (segundos) para cache in-memory de respuestas `get_product_info` | `0` (deshabilitado) |
| `MCP_REQUIRE_TOKEN` | Si `1`, exige token HMAC simple en header `X-MCP-Token` | `0` |
| `MCP_SHARED_TOKEN` | Token compartido cuando `MCP_REQUIRE_TOKEN=1` | (vacío) |

Ejemplo con token y debug:
```bash
curl -X POST http://localhost:8100/invoke_tool \
  -H 'Content-Type: application/json' \
  -H 'X-MCP-Token: supersecret' \
  -d '{"tool_name":"get_product_info","parameters":{"sku":"ABC123","user_role":"viewer"}}'
```

Ejemplo levantando el servicio con cache TTL y logging debug:
```bash
API_BASE_URL=http://localhost:8000 LOG_LEVEL=DEBUG MCP_CACHE_TTL_SECONDS=30 \
  uvicorn mcp_servers.products_server.main:app --reload --port 8100
```

## Manejo de errores (códigos HTTP)

| Código | Causa | Notas |
|--------|-------|-------|
| 400 | Parámetros inválidos (`sku`, `user_role`, formato JSON) | Validación inicial del dispatcher |
| 401 | Token ausente/incorrecto (si `MCP_REQUIRE_TOKEN=1`) | Header `X-MCP-Token` |
| 403 | Rol insuficiente (`get_product_full_info`) | `PermissionError` |
| 404 | Tool desconocida | Nombre no registrado |
| 502 | Error de red genérico / excepción interna | `httpx.RequestError` u otros |
| 504 | Timeout consultando API backend | `httpx.TimeoutException` |

Los errores de backend (status >= 400) en endpoints consultados se propagan como 502/504 con mensaje genérico para evitar fuga de detalles internos.

## Cache (in-memory)

- Al habilitar `MCP_CACHE_TTL_SECONDS > 0`, las respuestas de `get_product_info` se almacenan en un dict en memoria del proceso.
- Clave: `product_info:{sku}`.
- No existe invalidación activa más allá de la expiración por TTL. Futuro: invalidación proactiva vía webhook o tool de purga.
- Uso recomendado sólo para cargas de lectura intensiva de productos estables.

## Autenticación básica por token (opcional)

Modo simple para entornos internos o pre-producción:
1. Exportar `MCP_REQUIRE_TOKEN=1` y `MCP_SHARED_TOKEN=<valor>`.
2. El cliente debe enviar el header `X-MCP-Token` con el valor exacto.
3. Pensado como escalón previo a JWT/HMAC firmado temporal con expiry y claims.

## Logging

- Logger: `mcp_products.*`.
- Nivel configurable con `LOG_LEVEL`.
- Mensajes `DEBUG` incluyen cada URL consultada y eventos de cache HIT/SET.
- Errores de red y timeouts generan logs `WARNING`; excepciones imprevistas `ERROR` con stack (`logger.exception`).

## Roadmap inmediato (extensión futura)

- JWT / firma HMAC con expiración y claim de rol
- Cache distribuida o invalidación por eventos
- Métricas (prometheus): latencia p50/p95, tasa de error, top SKUs
- Tool de búsqueda parcial (`search_products`) con ranking
- Tool extendida (`get_product_full_info`) incorporando categoría, suppliers, historial de stock y precios

## Futuras expansiones sugeridas
- Cache interna TTL opcional para respuestas de productos consultados frecuentemente.
- Autenticación tokenizada + verificación de firma en lugar de confiar ciegamente en `user_role`.
- Normalización de errores hacia un código de respuesta MCP estándar (en caso de formalizar el protocolo completo).
- Métricas (latencia por tool, tasa de errores, top SKUs consultados).
- Herramientas adicionales: búsqueda por nombre parcial, historial de stock, ofertas por proveedor.

## Documentación a actualizar en el monorepo
- `Roadmap.md`: Añadir capa MCP Servers y referencia a este MVP.
- `AGENTS.md`: Notar la existencia de la carpeta `mcp_servers/` y lineamientos de expansión.
- `README.md` raíz: Sección breve sobre arquitectura con microservicios MCP.
- `docs/CHATBOT_ARCHITECTURE.md`: Integración futura del agente con MCP.

## Licencia
Mantiene la misma licencia del proyecto principal.
