<!-- NG-HEADER: Nombre de archivo: 2026-09-05-production-security-hardening.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-09-05-production-security-hardening.md -->
<!-- NG-HEADER: Descripción: Plan de endurecimiento para la primera puesta en producción -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Plan de endurecimiento para la primera puesta en producción

## Contexto

Preparar Growen para su primer despliegue productivo, accesible desde cualquier dispositivo de la LAN mediante `192.168.100.100`. El diagnóstico sobre `ENV=dev` se trata como bloqueante previo al despliegue, no como una vulnerabilidad actualmente explotada en producción.

## Observaciones

- Proteger las descargas de adjuntos y logs de compras con sesión y rol `admin|colaborador`, validación de pertenencia y respuestas no enumerables.
- Adoptar secretos externos para PostgreSQL y demás integraciones; ninguna contraseña deberá aparecer en argumentos, logs ni comandos construidos dinámicamente.
- Permitir CORS únicamente para los orígenes exactos del frontend alojado en `192.168.100.100`, sin comodines.
- Conservar el túnel MeLi exclusivamente para callback y webhook. La aplicación administrativa no se publicará en Internet.

## Errores y/u outputs de referencia

- Riesgos prioritarios: descargas públicas, API productiva heredando `dev`, endpoint de variables de entorno, SSRF y mezcla de archivos públicos/privados.
- Dependencias: `pip-audit` y `npm audit` sin vulnerabilidades conocidas en la línea base auditada.
- Gates existentes: autenticación/endurecimiento `9 passed`; MeLi/aislamiento `14 passed`.
- Deuda de pruebas: `test_frontend_diag.py` ejecuta cuatro casos, pero falla durante teardown por la tarea de archivado de Chat.

## Objetivo

Dejar una configuración productiva fail-closed, con autenticación y CSRF efectivos, TLS LAN, secretos externos, superficies de diagnóstico deshabilitadas, archivos privados fuera del montaje público, SSRF robusto e invalidación de sesiones ante cambios de credenciales o estado.

## Propuesta de código o pasos

1. Cerrar las exposiciones directas en compras y diagnóstico.
2. Separar `PUBLIC_MEDIA_ROOT` y `PRIVATE_MEDIA_ROOT`, incorporar descargas privadas y proveer una migración local idempotente con `--dry-run` y `--apply` que conserve originales y verifique SHA-256.
3. Configurar el stack productivo con `ENV=production`, autenticación, cookies seguras, orígenes LAN exactos, proxy explícito, TLS y validación de arranque fail-closed.
4. Incorporar cabeceras HTTP defensivas y hosts confiables.
5. Endurecer las descargas remotas contra SSRF, redirecciones, DNS rebinding, exceso de tamaño y MIME no permitido.
6. Completar la transición a `*_FILE`/Docker Secrets y ejecutar `pg_dump` sin shell ni contraseña en argumentos.
7. Llevar el rate limit de login a Redis, evitar datos identificatorios en logs, invalidar sesiones y corregir el shutdown del archivador de Chat.
8. Ejecutar suites focales, auditorías y validaciones de Compose/Swarm; actualizar documentación viva.

## Criterios de aceptación

- El acceso anónimo a adjuntos, logs y media privada no revela la existencia del recurso.
- Ningún endpoint productivo enumera sesiones ni variables de entorno.
- El stack renderizado declara producción, secretos externos, TLS y orígenes LAN exactos.
- Una prueba `no_auth_override` cubre login, `/auth/me`, CSRF válido e inválido y una descarga privada.
- SSRF rechaza IPs privadas, metadata cloud, nombres Docker internos, DNS rebinding y redirecciones bloqueadas.
- Un cambio o restablecimiento de contraseña y la desactivación de usuario invalidan sesiones anteriores.
- Bandit, `pip-audit`, ambos `npm audit`, escaneo redactado, suites focales, validación Compose/Swarm y teardown frontend terminan con código cero.
- Se documentan todos los cambios y se actualiza cualquier información desactualizada.
- El smoke autenticado final se ejecuta desde otro dispositivo de la LAN contra `https://192.168.100.100` antes del despliegue.
- No se ejecutan stage, commit, push, despliegue ni migración efectiva sin autorización explícita.

## Rollback

- Los archivos privados se copian y verifican; los originales no se eliminan automáticamente.
- La activación productiva se realiza sólo después de validar secretos, certificado con IP SAN y orígenes.
- Ante una regresión se revierte la configuración al stack previo y se conservan manifiestos y hashes para comparar, sin destruir datos.
