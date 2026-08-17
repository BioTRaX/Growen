<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_CHAT_TELEGRAM_20260815.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_CHAT_TELEGRAM_20260815.md -->
<!-- NG-HEADER: Descripción: Retrospectiva factual del avance seguro de Chat, Telegram y Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — Chat 😎 y Telegram seguro

Fecha: 2026-08-15.

## Contexto

La sesión continuó el plan multicanal sin configurar API keys, habilitar flags,
iniciar el worker Telegram ni publicar `/chat` en Vue. Los secretos expuestos ya
habían sido rotados por el usuario.

## Evidencia de entrega

- La API dejó de montar y conservar el router webhook; la configuración sólo
  acepta `TELEGRAM_TRANSPORT=polling`.
- El estado seguro del worker se agrega a métricas mediante una lista explícita
  de campos, sin IDs, mensajes, tokens ni errores crudos.
- Vue incorpora gestión de vínculos propios y aprobación/revocación por segundo
  administrador con identificadores enmascarados y cierre por flags.
- WebSocket recarga el rol de cuenta por mensaje y pasa tools, fallback local,
  respuesta general y streaming por `ChatOrchestrator`.
- El historial usa presupuesto aproximado por tokens y conserva el orden
  cronológico; la trazabilidad registra estimaciones sin persistir contenido.
- Los logs de historial, Telegram y diagnóstico dejaron de incluir sujetos
  opacos, paths, estado conversacional, consultas extraídas y excepciones crudas.
- La suite consolidada de la sesión aprobó 50 pruebas y omitió 6. Vue aprobó
  typecheck, 89 pruebas y build. Tras el último endurecimiento, la suite focal
  volvió a aprobar 12 pruebas.

## Obstáculos y solución aplicada

1. La prueba inicial de ausencia de webhook asumía que todos los elementos de
   `app.routes` tenían `path`; el wrapper interno `_IncludedRouter` no cumple ese
   contrato. Se cambió a acceso defensivo con `getattr`.
2. Un intento de probar cambio de rol con mensajes WebSocket arbitrarios entró
   en la detección legacy de productos y no ejercitó el proveedor simulado. Se
   aisló el contrato real en una prueba async de recarga de sesión/rol.
3. JSDOM no implementa `HTMLElement.scrollTo`; la spec de streaming falló por el
   entorno, no por el componente. Se agregó un stub local en la prueba.
4. Windows rechazó una ejecución de la venv con `Acceso denegado`; se repitió el
   mismo comando con permiso elevado y finalizó correctamente.

## Deuda residual verificada

- Las respuestas de aclaración heredadas de `/ws` aún no pasan por el
  orquestador común.
- Tokens y costos son estimados; el usage real requiere un proveedor configurado
  y no debe probarse mientras el entorno permanezca sin API keys.
- Las pruebas heredadas con `TestClient` emiten una deprecación y warnings por
  conexiones `aiosqlite` no devueltas al pool.
- Faltan evaluaciones RAG con corpus clasificado, smoke autenticado por los cinco
  roles y validación distribuida con Redis del rate limit/reinicio/backpressure.
- Continúan pendientes la protección automática de secretos y la purga de refs
  históricas administradas por GitHub, documentadas en la retrospectiva forense.

## Mejoras reutilizables

- Mantener pruebas unitarias de adaptadores de infraestructura separadas de la
  heurística conversacional; los smokes integrales deben usar intenciones
  controladas y afirmar explícitamente la rama ejecutada.
- Proveer en fixtures un polyfill compartido de APIs DOM ausentes cuando varios
  componentes dependan de ellas, en lugar de repetir stubs por spec.
- Migrar gradualmente los tests WebSocket desde `TestClient` a un cliente async
  con ciclo de vida explícito para cerrar engines y eliminar warnings de pool.
- Añadir al quality gate una búsqueda redactada de patrones prohibidos en logs:
  IDs externos, contenido de mensajes, paths de medios, tokens y URLs de base.

## Criterio de cierre

La base implementada queda lista para revisión con flags apagados y sin
credenciales. El siguiente gate no es activar Telegram: es cerrar warnings y
aclaraciones WebSocket, cargar un corpus RAG clasificado y ejecutar smokes con
claves efímeras fuera del repositorio. Toda evolución debe documentar cambios y
actualizar cualquier contenido que quede desactualizado.
