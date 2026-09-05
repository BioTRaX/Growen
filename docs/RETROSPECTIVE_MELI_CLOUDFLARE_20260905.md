<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_MELI_CLOUDFLARE_20260905.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_MELI_CLOUDFLARE_20260905.md -->
<!-- NG-HEADER: Descripción: Cierre factual de activación Cloudflare y OAuth MeLi. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Cierre de activación MeLi y Cloudflare

## Contexto

Sesión del 4 y 5 de septiembre de 2026. Se activó infraestructura y código MeLi preexistente en un worktree con muchos cambios ajenos. No se realizó commit, push ni despliegue Swarm. El usuario cierra esta sesión y reserva el gestor de imágenes para otra.

## Observaciones

- Cloudflare conectado; gateway y worker saludables al cierre.
- HTTPS verificado: callback incompleto 422, webhook GET 405 y health público bloqueado 404.
- OAuth real completado: cuenta activa en PostgreSQL, ambos ciphertext presentes, estado de un uso consumido y scopes de 505 caracteres. El callback exitoso sólo ocurre después del intercambio, consulta de identidad y commit.
- 12 pruebas aprobadas: gateway, OAuth/webhooks, migración incremental y reversión protegida, cadena completa en PostgreSQL temporal. Head local `20260905_meli_scopes_text`; columna confirmada como TEXT.
- No se probaron notificaciones POST reales, stock real, renovación de tokens ni inicio OAuth por API autenticada con CSRF. Los enlaces iniciales fueron generados administrativamente mediante la función existente dentro del gateway, con solicitante nulo y sin atribuir identidad autenticada.

## Errores y/u outputs

1. Token con extensión `.txt`: renombrado fuera del repositorio para coincidir con Compose; no se mostró su contenido.
2. Conector pendiente: arrancado `meli_cloudflared` de forma aislada. El formulario requería protocolo dentro de Service URL; se corrigió la indicación a `http://meli_webhook_gateway:8080`.
3. CNAME sin proxy: resolvía a dirección privada del túnel pese a estado Healthy. El usuario activó Proxied; DNS autoritativo y HTTPS quedaron verificados.
4. Mensaje falso de vencimiento: `state` vigente, no consumido y PKCE correcto, pero faltaba refresh token. Se incorporó diagnóstico de lista cerrada, solicitud explícita de `offline_access` y mensaje específico; el usuario habilitó el permiso en DevCenter.
5. Fallo posterior de persistencia: VARCHAR(500) rechazaba permisos de 505 caracteres. Migración incremental a TEXT, sin truncar datos ni editar historia; downgrade protegido frente a pérdida. OAuth real exitoso después del despliegue.
6. Restricciones iniciales de ejecución requirieron escalaciones; no eran fallos de Docker o Python. Un comando diagnóstico tuvo un error de paréntesis, corregido antes de ejecutarse correctamente.
7. `alembic check` continúa detectando drift histórico global; no se declara esquema global limpio. Se conservaron cambios ajenos.

## Objetivo

Preservar la evidencia de una cuenta realmente vinculada, separándola de las pruebas operativas del worker que aún faltan.

## Propuesta de código o pasos

| Mejora | Evidencia y frecuencia | Beneficio / mantenimiento | Recomendación |
|---|---|---|---|
| Diagnóstico de callback sin secretos | Mensaje de expiración ocultó dos causas; recurrente en OAuth | Evita reautorizaciones ciegas; costo bajo | Diagnóstico y pruebas ya incorporados |
| Prueba de scopes extensos en PostgreSQL | SQLite no impone VARCHAR; posible ante cambios de permisos | Detecta límites reales; costo bajo | Prueba incremental y fresh incorporadas |
| Preflight de activación | Se repitieron comprobaciones de archivos, DNS, health y head | Reduce pasos manuales; costo medio | Futuro recurso determinista de diagnose-local-services, sin modificar skills en este cierre |
| Flujo admin de vinculación visible | No había API local escuchando; enlaces generados por operación administrativa | Facilita reautorizar y auditar; costo medio | Planificar UI/API autenticada y smoke CSRF |

## Criterios de aceptación

- Cambios documentados y referencias de estado actualizadas en README, Roadmap, integración y migraciones.
- Ningún token, código OAuth, enlace temporal o clave incluido en este informe.
- Cuenta activa confirmada; pruebas de negocio pendientes explícitas.
- Servicios quedan ejecutándose para conservar la integración. No se archiva ni se apagan servicios automáticamente.
