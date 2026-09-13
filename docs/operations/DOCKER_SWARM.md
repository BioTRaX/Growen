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

## Errores y/u outputs bloqueantes

El rollout debe abortar ante una imagen sin digest, secreto faltante, SAN incorrecto, hallazgo HIGH/CRITICAL de Trivy, tarea Alembic fallida, réplica pendiente o configuración Swarm no renderizable. Un Swarm de un nodo no debe desplegarse con `-Topology HA`.

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
4. Cargar el entorno generado con las imágenes por digest y definir `LAN_TLS_CERT_SECRET`, `LAN_TLS_KEY_SECRET` y los secretos externos restantes.
5. Validar sin mutar:

   ```powershell
   .\scripts\deploy-swarm.ps1 -Phase Preflight -Topology SingleNode
   ```

6. Con autorización de despliegue, ejecutar `Bootstrap`; esperar PostgreSQL saludable y Alembic terminado en `20260909_user_active`.
7. Auditar `users.is_active` y recién entonces ejecutar `Application`.
8. Confirmar que API, PostgreSQL y Redis no publican puertos, que no hay tareas `Rejected/Failed` y que los cuatro volúmenes externos son los esperados.

### 4. Smoke LAN

Desde otro dispositivo con la CA instalada, proporcionar `ADMIN_USER_FILE`, `ADMIN_PASS_FILE`, `SMOKE_CA_BUNDLE` y ejecutar `scripts/test_login_flow.py`. Validar además navegador sin advertencias, CORS exacto, CSRF válido/inválido, cookie `Secure`, descarga privada autorizada y `404` no enumerable para accesos anónimos.

### 5. Coexistencia con Dev y ciclo de actualización continua

#### A. Transición desde Docker Compose (Resolución de colisiones de red)
- Si el stack de desarrollo (`docker-compose.yml`) estuvo en ejecución, Docker Engine conservará redes tipo `bridge` locales con el prefijo del proyecto (`growen_backend`, `growen_egress`, etc.).
- Docker Swarm fallará con `network with name growen_backend already exists` al intentar crear sus redes `overlay` homónimas si las redes bridge siguen activas.
- **Regla obligatoria**: Antes de desplegar el stack Swarm, ejecutar `docker compose down` (estrictamente **sin** el parámetro `-v`) para liberar los nombres de red conservando intactos los volúmenes de datos (`growen_pgdata`, medios, etc.).

#### B. Reutilización de Base de Datos y sincronización de contraseñas
- El servicio `db` de Swarm reutiliza el volumen persistente `growen_pgdata` creado en desarrollo.
- Si se crea el secreto Swarm `postgres_password` con una credencial distinta a la que tenía PostgreSQL en desarrollo (`.env`), el motor no modificará la contraseña de usuario (`initdb` sólo se ejecuta en directorios de datos vírgenes).
- Para evitar fallos de autenticación de la API (`password authentication failed for user "growen"`), sincronizar la clave de la base con el secreto montado en Swarm:
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

- La cadena Alembic limpia alcanza `20260909_user_active` antes de arrancar la API.
- Todas las imágenes desplegadas están fijadas por digest, aprobadas por Trivy y acompañadas por SBOM.
- `.100` queda estable, el certificado tiene IP SAN y los clientes confían en la CA.
- La topología de un nodo no deja réplicas pendientes ni declara alta disponibilidad.
- La media privada conserva originales y verifica hashes.
- El smoke autenticado desde otro dispositivo termina satisfactoriamente.
- No se ejecutan migración, cambio de red, creación de secretos, despliegue, stage, commit ni push sin su autorización correspondiente.
- Se documentan todos los cambios y se actualiza cualquier información desactualizada.
