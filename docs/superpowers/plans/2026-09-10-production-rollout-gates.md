<!-- NG-HEADER: Nombre de archivo: 2026-09-10-production-rollout-gates.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-09-10-production-rollout-gates.md -->
<!-- NG-HEADER: Descripción: Plan ejecutable de compuertas para el primer rollout productivo LAN -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Compuertas para el primer rollout productivo LAN

## Contexto

Growen se prepara para una primera producción de un nodo en `192.168.100.100`. El código, las imágenes y la infraestructura deben quedar reproducibles antes de autorizar cambios sobre red o datos.

## Observaciones

- PKI, registro, bootstrap, análisis de imágenes y topología de un nodo se implementan como piezas independientes y previsualizables.
- Los reportes permanecen locales; SiYuan es el único destino documental privado.
- Los secretos y credenciales se leen desde archivos y no aparecen en argumentos ni logs.

## Errores y/u outputs

Son bloqueantes: migración Alembic fallida, imagen sin digest, Trivy HIGH/CRITICAL, TLS sin IP SAN, secreto ausente, réplica fallida o smoke LAN con advertencia de certificado.

## Objetivo

Llegar a una decisión de despliegue respaldada por pruebas, manifiestos, SBOM, backup restaurable y autorizaciones operativas explícitas.

## Propuesta de código o pasos

1. Validar scripts, manifests y suites sin mutar infraestructura.
2. Separar y revisar documentalmente los cambios concurrentes antes de cualquier stage.
3. Provisionar red, PKI y registro sólo con autorización operativa.
4. Construir desde un SHA, analizar, publicar y registrar digests.
5. Ejecutar dry-run de media y prueba Alembic efímera.
6. Solicitar autorizaciones independientes para aplicar media y desplegar.
7. Ejecutar Bootstrap, auditar esquema y ejecutar Application.
8. Completar smoke desde otro dispositivo y recién entonces solicitar integración Git.

## Criterios de aceptación

- Cada paso deja evidencia reproducible y admite rollback sin borrar originales.
- No existe dependencia, configuración ni runtime de Notion; la documentación privada queda en SiYuan.
- Todas las compuertas automatizadas terminan con código cero.
- Se documentan todos los cambios y se actualiza cualquier información desactualizada.

## Estado al 2026-09-10

- Implementados y verificados: PKI desechable con IP SAN, registro renderizable, scripts de build/Trivy/SBOM, bootstrap, override de un nodo, Alembic sobre PostgreSQL efímero, smoke por archivos, HMAC y retiro del runtime de Notion.
- El dry-run local detectó 60 archivos de compras con estado `would_copy`; no se aplicó la migración.
- El gate Ruff oficial y el conjunto modificado terminan en cero. Un barrido informativo del árbol completo detecta 798 incidencias legacy fuera de esta entrega; queda como bloqueante documentado antes de exigir Ruff global en producción.
- La interfaz Ethernet quedó verificada en `192.168.100.100/24`, estado `Preferred`, configuración manual y gateway `192.168.100.1` alcanzable sin pérdida. Los DNS configurados son `8.8.8.8` y `8.8.8.6`; no se modificaron.
- La PKI persistente vigente `2026091002` fue generada fuera del repositorio con IP SAN y AKI; sus secretos TLS versionados existen en Swarm. La primera versión `20260910` se conserva, pero no debe desplegarse porque no incluía AKI.
- El registro privado está activo y saludable en `192.168.100.100:5000`; TLS estricto con CA explícita y autenticación fueron verificados (`401` anónimo, `200` autenticado).
- Pendientes de intervención: reservar o excluir `.100` en DHCP, crear las reglas LAN desde PowerShell elevado, importar la CA vigente en el almacén del equipo local y reiniciar Docker Desktop.
- Pendientes posteriores: login/push/pull Docker, build/scan/push real, migración de media, despliegue y smoke desde otro dispositivo.
