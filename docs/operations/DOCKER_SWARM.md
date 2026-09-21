<!-- NG-HEADER: Nombre de archivo: DOCKER_SWARM.md -->
<!-- NG-HEADER: Ubicación: docs/operations/DOCKER_SWARM.md -->
<!-- NG-HEADER: Descripción: Despliegue LAN reproducible de Growen en Docker Swarm -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Docker Swarm productivo

## Contexto

La primera producción de Growen operará en un Swarm de un nodo, accesible sólo en la LAN mediante `https://192.168.100.100`. Esta topología no ofrece alta disponibilidad. El túnel Cloudflare continúa aislado y publica únicamente callback y webhook de MeLi.

## Observaciones

- `docker-stack.bootstrap.yml` inicia PostgreSQL, Redis y una tarea Alembic antes de la aplicación.
- `docker-stack.single-node.yml` reduce todos los servicios replicados a una tarea.
- `docker-stack.yml` exige las trece variables `GROWEN_*_IMAGE` en formato inmutable `tag@sha256:digest`.
- Los volúmenes `growen_pgdata`, `growen_redis_data`, `growen_public_media` y `growen_private_media` son externos.
- El registro privado se define en `infra/registry/docker-compose.registry.yml`, escucha sólo en `192.168.100.100:5000` y exige TLS más `htpasswd` bcrypt.
- La documentación privada y operativa se conserva en SiYuan; no hay publicación automática de reportes de errores a servicios externos.
- La generación de PKI requiere PowerShell 7 o posterior por las APIs criptográficas utilizadas. Las hojas incluyen Authority Key Identifier (AKI), además del IP SAN, para que los clientes estrictos puedan construir la cadena.
- `catalog_audit_worker` consume exclusivamente la cola `catalog_audit` con un proceso y un thread. Ollama permanece en el host y se alcanza mediante `host.docker.internal`; el worker de Enrich monta `openai_api_key` y conserva la prioridad OpenAI → Ollama.

## Errores y/u outputs bloqueantes

El rollout debe abortar ante una imagen sin digest, secreto faltante, SAN incorrecto, hallazgo HIGH/CRITICAL de Trivy, tarea Alembic fallida, réplica pendiente o configuración Swarm no renderizable. Un Swarm de un nodo no debe desplegarse con `-Topology HA`; los servicios limitados a una réplica por nodo usan `stop-first` en esta topología para evitar que una actualización quede bloqueada esperando un segundo nodo.

## Objetivo

Desplegar exactamente las imágenes construidas desde un commit revisado, con esquema actualizado antes de la API, TLS confiable, media privada separada y evidencia reproducible de análisis y digests.

## Propuesta de código o pasos

### 1. Preflight de red y PKI

Estado verificado el 2026-09-10: Ethernet usa `192.168.100.100/24` manual,
Windows la informa `Preferred`, el gateway `192.168.100.1` está activo y
responde sin pérdida. Los DNS actuales son `8.8.8.8` y `8.8.8.6`; confirmar si
esa elección es intencional antes del despliegue.

1. Verificar en el router que `.100` esté libre y fuera del pool DHCP. La interfaz Ethernet del servidor tiene MAC `2C-F0-5D-59-D2-A7`; usarla para una reserva DHCP si el router lo permite.
2. Conservar el registro de IP, gateway y DNS verificados antes de otros cambios.
3. Restringir `80`, `443` y `5000` a `192.168.100.0/24` mediante Firewall de Windows.
4. Ejecutar primero:

   ```powershell
   .\scripts\provision-lan-pki.ps1 -IPAddress 192.168.100.100 -OutputDir <ruta-externa> -RootKeyPasswordFile <archivo-externo> -WhatIf
   ```

5. Repetir sin `-WhatIf` sólo tras autorización. Instalar `growen-lan-root-ca.crt` en Windows, Docker Desktop y cada cliente autorizado. Las hojas web y registro duran hasta 397 días y contienen IP SAN y AKI enlazado con la CA.
6. Crear secretos versionados sin borrar los anteriores. La versión vigente es `lan_tls_cert_2026091002` y `lan_tls_key_2026091002`; los secretos `20260910` se conservan para trazabilidad, pero no deben desplegarse porque sus hojas no contenían AKI.

Estado operativo del 2026-09-10:

- La PKI vigente está fuera del repositorio en `C:\Users\alete\.growen\pki\2026091002`; su CA tiene huella SHA-1 `314D2EBE85AEABD00F091BE25D243337827A7A1C` para verificación visual durante la importación.
- Los secretos Swarm `lan_tls_cert_2026091002` y `lan_tls_key_2026091002` existen y no reemplazaron ni eliminaron versiones anteriores.
- Falta importar la CA vigente en `Entidades de certificación raíz de confianza` del equipo local y reiniciar Docker Desktop.
- Las reglas de firewall no se crearon: Windows respondió `Acceso denegado` en una consola sin elevación.

### 2. Registro e imágenes

1. Preparar un archivo `htpasswd` bcrypt fuera del repositorio y montar PKI/autenticación según las variables del compose del registro.
2. El registro `growen-registry` está activo y saludable con la PKI `2026091002`. La verificación HTTPS con la CA explícita devuelve `401` sin credenciales y `200` autenticado. El login del daemon Docker, el push y el pull de la imagen sonda quedan bloqueados hasta importar la CA en Windows y reiniciar Docker Desktop.
3. Previsualizar el pipeline:

   ```powershell
   .\scripts\build-scan-push.ps1 -Registry 192.168.100.100:5000 -SourceRevision <SHA> -RegistryPasswordFile <archivo> -OutputDir backups/security/<SHA> -WhatIf
   ```

4. La ejecución efectiva construye diez imágenes, refleja Redis/SiYuan/Cloudflared, usa la imagen oficial fijada de Trivy, bloquea HIGH/CRITICAL, genera SBOM CycloneDX y produce `images.manifest.json` e `images.env.ps1` bajo `backups/security/<SHA>/`.

### 3. Migraciones y despliegue

1. Validar la cadena Alembic en PostgreSQL desechable:

   ```powershell
   .\scripts\test-postgres-migrations.ps1 -PostgresImage <imagen-pgvector-por-digest>
   ```

2. Crear backup lógico y comprobar su restauración antes de tocar producción.
3. Ejecutar `scripts/migrate_private_media.py --dry-run`; aplicar la copia sólo con autorización separada y conservar originales.
4. Cargar el entorno generado con las imágenes por digest y definir `LAN_TLS_CERT_SECRET`, `LAN_TLS_KEY_SECRET` y los secretos externos restantes, incluido `openai_api_key`.
5. Validar sin mutar:

   ```powershell
   .\scripts\deploy-swarm.ps1 -Phase Preflight -Topology SingleNode
   ```

6. En la primera instalación, ejecutar `Bootstrap`. Si la aplicación ya está activa, ejecutar `Migration`; esta fase rechaza migraciones concurrentes, recrea sólo una tarea Alembic terminal y espera el head `20260913_catalog_audit_v1`.
7. Auditar `users.is_active`, las tablas `catalog_audit_*` y las columnas de auditoría de `canonical_products`; recién entonces ejecutar `Application`.
8. Confirmar que API, PostgreSQL y Redis no publican puertos, que no hay tareas `Rejected/Failed`, que `catalog_audit_worker` converge 1/1 y que los cuatro volúmenes externos son los esperados.

Estado verificado el 2026-09-14: backup lógico restaurado en PostgreSQL aislado,
head productivo `20260913_catalog_audit_v1`, 18 servicios en 1/1 y ninguna tarea
actual con error. Las imágenes en ejecución coinciden con los digests del
manifiesto, `/health`, `/api/health` y el health del auditor responden 200, y el
worker alcanzó `llama3.1:8b` con contexto 4096 al 100 % GPU. El smoke
autenticado automatizado no se declaró aprobado: el secreto de bootstrap
`admin_pass` no coincide con las credenciales de los dos administradores activos
y debe alinearse o ejecutarse con credenciales operativas sin rotarlas durante
este rollout.

Estado verificado el 2026-09-20:
- Base de datos productiva (`growen_pgdata`) alineada al 100 % desde el volcado lógico de `dev`, transfiriendo 11 corridas de auditoría, 123 ítems auditados, 13 feedbacks, 59 trabajos de enriquecimiento, 173 activos de conocimiento y 43 versiones de contenido sin necesidad de reauditar el catálogo.
- Volúmenes externos de media actualizados: `growen_public_media` (logos corporativos) y `growen_private_media` (comprobantes y remitos de compras). Ambos volúmenes deben pertenecer a `app:app` (`uid:gid 100:101`) con permisos de escritura; de lo contrario, la subida de comprobantes temporales en compras arroja `PermissionError: [Errno 13]`. Corrección inmediata si fueron inicializados como root: `docker exec -u 0 <container_id> chown -R app:app /data/media`.
- Imágenes inmutables reconstruidas bajo la revisión `325fba480aa9aa000a78b385bf4c5283180fd964`, escaneadas con Trivy, publicadas en el registro privado LAN (`192.168.100.100:5000`) y desplegadas en el Swarm (`SingleNode`).
- Los 18 servicios Swarm convergen en estado 1/1 y saludables. Comprobados `/health` (200), `/api/health` (200) y `/api/health/summary` (200 con DB, Redis, Storage y 7 workers activos: market, enrichment, catalog_audit y canonical_knowledge).

Estado verificado el 2026-09-21:
- Se activó `ENRICH_V2_ENABLED=1` en el entorno común Python de `docker-stack.yml` (`x-python-env`). Anteriormente el valor por defecto `"0"` bloqueaba el despacho de jobs desde el worker de auditoría y desde la API, dejando los jobs de enriquecimiento estancados en `queued` y la corrida en `waiting_enrich`.
- Se montó el secreto Swarm `mcp_web_search_secret_key` y la variable `MCP_WEB_SEARCH_SECRET_KEY_FILE` en `growen_enrichment_worker`. Esto permite al worker firmar los JWT requeridos para comunicarse con el servidor `mcp_web_search:8002`.
- Se convergieron los servicios `growen_api`, `growen_catalog_audit_worker` y `growen_enrichment_worker`, y se completó la corrida de auditoría que se encontraba estancada.

### 4. Smoke LAN

Desde otro dispositivo con la CA instalada, proporcionar `ADMIN_USER_FILE`, `ADMIN_PASS_FILE`, `SMOKE_CA_BUNDLE` y ejecutar `scripts/test_login_flow.py`. Validar además navegador sin advertencias, CORS exacto, CSRF válido/inválido, cookie `Secure`, descarga privada autorizada y `404` no enumerable para accesos anónimos.

### 5. Coexistencia con Dev y ciclo de actualización continua

#### A. Aislamiento estricto de volúmenes y redes (Dev vs Swarm)
- El entorno de desarrollo (`docker-compose.yml`) utiliza explícitamente el volumen persistente `growen_dev_pgdata` y redes dedicadas (`growen_dev_backend`, `growen_dev_host_access`, etc.).
- Docker Swarm utiliza de forma independiente `growen_pgdata` y redes overlay con el prefijo del stack (`growen_backend`, etc.).
- Este desacoplamiento previene dos riesgos mayores:
  1. **Corrupción de PostgreSQL**: dos instancias de PostgreSQL nunca deben montar concurrentemente el mismo volumen de datos físico.
  2. **Colisión de nombres de red**: Compose no interfiere con las redes overlay creadas por el despliegue de Swarm.

#### B. Clonación y sincronización inicial de Base de Datos
- Para inicializar o actualizar la base de desarrollo desde Swarm sin afectar producción:
  ```powershell
  # 1. Exportar dump lógico desde el contenedor Swarm
  $swarmDb = (docker ps -q -f name=growen_db | Select-Object -First 1)
  docker exec $swarmDb pg_dump -U growen -d growen -F c -f /tmp/growen_swarm.dump
  docker cp ${swarmDb}:/tmp/growen_swarm.dump tmp/growen_swarm.dump
  docker exec $swarmDb rm /tmp/growen_swarm.dump

  # 2. Restaurar en el contenedor dev local
  $devDb = (docker ps -q -f name=growen-postgres | Select-Object -First 1)
  docker cp tmp/growen_swarm.dump ${devDb}:/tmp/growen_swarm.dump
  docker exec $devDb pg_restore -U growen -d growen --no-owner --no-privileges /tmp/growen_swarm.dump
  docker exec $devDb rm /tmp/growen_swarm.dump
  Remove-Item tmp/growen_swarm.dump -Force
  ```
- Si se crea el secreto Swarm `postgres_password` con una credencial distinta a la que tenía PostgreSQL en desarrollo (`.env`), el motor no modificará la contraseña de usuario (`initdb` sólo se ejecuta en directorios de datos vírgenes). Para sincronizar la clave de la base con el secreto montado en Swarm:
  ```powershell
  $db = (docker ps -q -f name=growen_db | Select-Object -First 1)
  docker exec $db sh -c 'psql -U growen -d growen -c "ALTER USER growen WITH PASSWORD '\''$(cat /run/secrets/postgres_password)'\'';"'
  ```

#### C. Replicación de cambios desde Dev hacia Swarm en Producción
- **Código (Backend / Frontend / Workers / MCP)**:
  1. Recompilar la imagen del servicio modificado (ej. `docker build -f infra/Dockerfile.api -t growen/api:production .`).
  2. Actualizar el servicio en caliente con rolling update:
     ```powershell
     docker service update --image growen/api:production growen_api
     ```
     *(Gracias a `update_config: {order: start-first}`, Swarm levanta la réplica nueva, valida el healthcheck y recién entonces retira el contenedor anterior, garantizando zero-downtime)*.
- **Esquema de Base de Datos (Migraciones Alembic)**:
  1. Recompilar la imagen que contiene las nuevas migraciones en `db/migrations/versions/`.
  2. Ejecutar la migración directamente en el contenedor API o mediante tarea administrativa antes de actualizar el resto de los consumidores:
     ```powershell
     $api = (docker ps -q -f name=growen_api | Select-Object -First 1)
     docker exec $api alembic upgrade head
     ```
- **Datos puntuales**: Para sincronizar catálogos o registros sin pisar transacciones de producción, exportar con `docker exec growen-postgres pg_dump -U growen -d growen --data-only -t <tabla>` e importar con `docker exec -i <growen_db> psql -U growen -d growen`.
- **Secretos**: Los secretos en Swarm son inmutables. Para rotar credenciales, crear un secreto versionado (ej. `secret_key_v2`) y actualizar el servicio (`docker service update --secret-rm ... --secret-add ...`).

## Criterios de aceptación

- La cadena Alembic limpia alcanza `20260913_catalog_audit_v1` antes de actualizar la API y los workers.
- Todas las imágenes desplegadas están fijadas por digest, aprobadas por Trivy y acompañadas por SBOM.
- `.100` queda estable, el certificado tiene IP SAN y los clientes confían en la CA.
- La topología de un nodo no deja réplicas pendientes ni declara alta disponibilidad.
- La media privada conserva originales y verifica hashes.
- El smoke autenticado desde otro dispositivo termina satisfactoriamente.
- No se ejecutan migración, cambio de red, creación de secretos, despliegue, stage, commit ni push sin su autorización correspondiente.
- Se documentan todos los cambios y se actualiza cualquier información desactualizada.
