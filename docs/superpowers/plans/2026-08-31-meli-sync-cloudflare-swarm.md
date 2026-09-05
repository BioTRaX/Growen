<!-- NG-HEADER: Nombre de archivo: 2026-08-31-meli-sync-cloudflare-swarm.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-08-31-meli-sync-cloudflare-swarm.md -->
<!-- NG-HEADER: Descripción: Plan de implementación de MeLi transaccional, Cloudflare Tunnel y Docker Swarm. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Plan de implementación de MeLi, Cloudflare y Swarm

> **Para workers agénticos:** ejecutar en línea tarea por tarea, con pruebas antes de implementación. No hacer stage, commit ni push sin autorización explícita.

**Objetivo:** incorporar OAuth multicuenta, webhook durable, stock Growen → MeLi, Cloudflare Tunnel aislado y despliegue Swarm completo.

**Arquitectura:** gateway FastAPI y consumidor Dramatiq comparten una imagen, pero escalan por separado. PostgreSQL conserva secretos rotativos cifrados y el outbox; Redis transporta la cola exclusiva. Cloudflare sólo alcanza el gateway por una red dedicada.

**Stack:** Python 3.14.6, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Redis/Dramatiq, HTTPX, AES-GCM, Docker Compose, Docker Swarm y cloudflared 2026.8.3.

**Especificación:** `docs/superpowers/specs/2026-08-31-meli-sync-cloudflare-swarm-design.md`

## Restricciones globales

- Usar `C:/Proyectos/NiceGrow/Growen/.venv/Scripts/python.exe` o Docker para Python y pytest.
- Preservar los cambios locales existentes y editar `docker-compose.yml` de forma focal.
- No introducir secretos directos, imprimirlos ni incluir valores con formato real en fixtures.
- Todo archivo nuevo de código o Markdown lleva NG-HEADER; `README.md` es la excepción.
- Documentar comportamiento, infraestructura, migración, rollback y operación en README, Roadmap y docs.

### Tarea 1: Esquema y criptografía MeLi

**Archivos:** `db/models.py`, nueva revisión Alembic, `services/meli/settings.py`, `services/meli/crypto.py`, `tests/test_meli_security.py`, pruebas de migración.

- [ ] Escribir pruebas fallidas para configuración, cifrado con AAD, rotación y constraints.
- [ ] Crear modelos de cuentas, state OAuth, notificaciones, vínculos y jobs con índices/constraints.
- [ ] Crear revisión lineal posterior al head actual; bloquear downgrade si hay datos MeLi.
- [ ] Implementar settings fail-fast y lector de secretos por archivo reutilizando `agent_core.secrets`.
- [ ] Ejecutar pruebas focales, `alembic heads` y validación de metadata focal.

### Tarea 2: OAuth, cliente y webhook durable

**Archivos:** `services/meli/client.py`, `services/meli/oauth.py`, `services/meli/webhooks.py`, `services/meli/schemas.py`, `tests/test_meli_oauth.py`, `tests/test_meli_webhooks.py`.

- [ ] Probar generación PKCE/state, consumo único, expiración y callback sin fuga.
- [ ] Implementar cliente HTTP con Bearer en header, timeout, refresh único y clasificación 401/429/5xx.
- [ ] Probar tamaño/esquema/application/topic/resource, duplicados y persistencia antes de 200.
- [ ] Implementar webhook como aviso no confiable y outbox recuperable.

### Tarea 3: Stock y consumidor dedicado

**Archivos:** `services/meli/stock.py`, `services/jobs/meli_sync.py`, `workers/meli_sync.py`, `scripts/meli_worker_health.py`, `tests/test_meli_worker.py`.

- [ ] Probar ítem simple, variación, idempotencia, reintentos y rechazo multiorigen.
- [ ] Implementar publicación Growen → MeLi con confirmación posterior y resultado persistente.
- [ ] Implementar actores `meli_sync`, reconciliación y heartbeat sin importar `market_worker`.
- [ ] Probar que secretos/cola MeLi no llegan al worker analítico.

### Tarea 4: Gateway y API administrativa

**Archivos:** `services/meli/app.py`, `services/routers/meli.py`, `services/api.py`, `tests/test_meli_gateway.py`, `tests/test_meli_api.py`.

- [ ] Probar endpoints públicos, health y rutas admin con sesión/CSRF reales.
- [ ] Montar callback/webhook sólo en gateway y autorización/vínculos sólo en API principal.
- [ ] Aplicar límites de cuerpo, respuestas genéricas y logs estructurados redactados.

### Tarea 5: Compose, imagen y Cloudflare reproducible

**Archivos:** `infra/Dockerfile.meli-worker`, `docker-compose.yml`, `infra/cloudflare/meli-tunnel.example.json`, `scripts/provision-meli-tunnel.ps1`, `.env.example`, `.gitignore`.

- [ ] Crear imagen multi-stage 3.14.6 no-root, read-only y healthcheck.
- [ ] Agregar gateway, worker y cloudflared con redes `meli_ingress` y `cloudflare_egress`, sin puertos públicos.
- [ ] Montar secretos de sólo lectura y usar `--token-file`; fijar versión cloudflared.
- [ ] Implementar provisioning idempotente/WhatIf de túnel, hostname, rutas exactas, DNS y catch-all 404.
- [ ] Validar `docker compose config` y reglas de aislamiento mediante tests estáticos.

### Tarea 6: Stack Swarm completo

**Archivos:** `docker-stack.yml`, `scripts/deploy-swarm.ps1`, `docs/DOCKER_SWARM.md`, pruebas de manifiesto.

- [ ] Traducir servicios productivos de Growen a stack con imágenes etiquetadas, configs/secrets externos y redes overlay.
- [ ] Definir réplicas, placement, rolling update, rollback, restart policies y probes.
- [ ] Mantener PostgreSQL/Redis como servicios stateful con volúmenes y una sola réplica documentada; HA de datos queda como prerequisito de plataforma externa.
- [ ] Desplegar MeLi y dos réplicas cloudflared sobre nodos distintos cuando existan labels suficientes.
- [ ] Agregar preflight y `-WhatIf`; no inicializar Swarm ni desplegar automáticamente durante tests.

### Tarea 7: Documentación y verificación

**Archivos:** `docs/MELI_INTEGRATION.md`, `docs/SECURITY.md`, `docs/MIGRATIONS_NOTES.md`, `docs/DEVELOPMENT_WORKFLOW.md`, `README.md`, `Roadmap.md`, `CHANGELOG.md`, `AGENTS.md` si cambia inventario.

- [ ] Documentar setup, secretos, OAuth, tópicos, stock, túnel, rotación, rollback, logs y smoke.
- [ ] Actualizar inventarios y eliminar afirmaciones desactualizadas encontradas dentro del alcance.
- [ ] Ejecutar pruebas MeLi, migraciones focales, seguridad, `docker compose config`, validación Swarm y suite consolidada pertinente.
- [ ] Revisar diff final, escanear secretos y registrar cualquier prueba omitida con motivo exacto.
