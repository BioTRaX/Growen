<!-- NG-HEADER: Nombre de archivo: ENVIRONMENTS.md -->
<!-- NG-HEADER: Ubicación: docs/operations/ENVIRONMENTS.md -->
<!-- NG-HEADER: Descripción: Definición de entornos (Dev/Prod) y proceso de despliegue -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Entornos de Growen

Este documento define la arquitectura y los procesos operativos para los distintos entornos de la aplicación Growen.

## 1. Entorno de Desarrollo (Dev)

El entorno local está diseñado para maximizar la velocidad de iteración y facilitar la depuración.

- **Frontend Vue**: Servidor Vite local (`npm run dev`) con hot-reload en el puerto `5176`.
- **API Backend**: Uvicorn local con hot-reload en el puerto `8000`.
- **Base de Datos y Redis**: Contenedores Docker (gestionados vía Compose).
- **Herramientas de IA y Workers**: Ejecutados localmente o en contenedores auxiliares bajo demanda mediante el script `scripts/start-dev.ps1`.
- **Configuración**: Se rige por el archivo `.env.dev` ubicado en la raíz. Este archivo puede contener contraseñas triviales (ej. `local_password`) ya que su exposición no supone un riesgo real.

Para más detalles sobre cómo ejecutar este entorno, consulta [../development/DEVELOPMENT_WORKFLOW.md](../development/DEVELOPMENT_WORKFLOW.md).

## 2. Entorno de Producción (Prod)

El entorno de producción está diseñado para alta disponibilidad, seguridad y resiliencia. No utiliza procesos sueltos.

- **Orquestación**: Todo el stack (Frontend servido por Nginx, API, Workers, Base de datos) se levanta utilizando Docker Swarm (o un stack de Compose completo).
- **Gestión de Secretos**:
  - **ESTRICTAMENTE PROHIBIDO** dejar tokens, contraseñas o claves maestras en texto plano en el archivo `.env` de producción.
  - Se deben inyectar mediante variables del tipo `*_FILE` que apunten a secretos montados en el contenedor (Docker Secrets o rutas de host restringidas).
- **Configuración**: Se rige por un `.env` generado a partir de la plantilla `.env.prod.example`.

Para instrucciones sobre el despliegue a producción, consulta [DOCKER_SWARM.md](DOCKER_SWARM.md).

## 3. Promoción de Código (Quality Gate)

El código transita desde ramas efímeras hacia `dev` (integración) y finalmente hacia `main` (producción).

Debido a restricciones en la cuota de minutos de CI (ej. GitHub Actions), **el Quality Gate es un paso de validación manual y obligatorio** antes de realizar un merge hacia `main`.

### Procedimiento de Merge a `main`:
1. Asegurarse de estar en la rama correcta y con el estado limpio.
2. Ejecutar localmente el script de validación integral:
   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-quality.ps1
   ```
3. Si y solo si todos los chequeos (linting, tests unitarios, tests e2e, dependencias, types de frontend) resultan exitosos, se autoriza el merge de `dev` a `main`.
4. El despliegue de `main` hacia el entorno productivo puede realizarse siguiendo el flujo descrito en `DOCKER_SWARM.md` o usando `scripts/deploy-swarm.ps1`.
