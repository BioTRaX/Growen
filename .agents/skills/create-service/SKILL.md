---
name: create-service
description: Usar al crear o modificar un servicio HTTP/MCP, worker, scheduler o job asíncrono de Growen.
---

# Crear un servicio

1. Leer `AGENTS.md` y la documentación del dominio; decidir entre Dramatiq, scheduler, worker continuo o servidor HTTP/MCP.
2. Reutilizar el patrón más cercano bajo `services/jobs/`, `workers/` o `mcp_servers/`.
   Si el servicio muta documentos o bases de datos de SiYuan, aplicar
   `references/siyuan-mcp-mutations.md`.
3. Modelar explícitamente dependencias, productor, broker, consumidores, colas y modos local/Docker antes de implementar.
4. Agregar NG-HEADER, variables de entorno, timeouts, apagado seguro y eventos estructurados con `service`, `event`, identificador de trabajo, duración y resultado.
5. Usar `DB_URL = os.getenv("DB_URL") or settings.db_url` si el servicio crea un engine.
6. Proveer arranque con la venv e imagen Docker multi-stage Python 3.14.6, no-root y con healthcheck.
7. Verificar que puertos publicados y redes internas permitan alcanzar DB y broker desde cada modo de ejecución.
8. Integrar a `scripts/start-dev.ps1` solo si forma parte del entorno diario; incluir preflight de dependencias y una forma documentada de seguir logs.
9. Agregar tests unitarios, fallos externos y un smoke test que pruebe encolado, consumo y persistencia final.
10. Actualizar inventario, README, Roadmap y documentación del dominio.

Ante incidentes operativos, aplicar primero `diagnose-local-services` y conservar evidencia antes de recrear componentes.

Inspeccionar siempre la implementación actual; no asumir registros o rutas legacy.
