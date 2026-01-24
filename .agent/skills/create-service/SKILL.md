---
name: create-service
description: Crea un nuevo servicio backend (worker), genera sus scripts de arranque multiplataforma, configura Hot-Reload (watchdog) en Docker y lo registra en el Job Manager para que aparezca en el Panel Admin.
---

# Create New Service Skill

Usa esta skill cuando el usuario diga "crea un nuevo worker", "añade un servicio" o "necesito un proceso para X".

## 🚨 When to use this skill

* Cuando el usuario quiera crear un nuevo worker o servicio backend.
* Cuando se necesite un proceso que corra en segundo plano.
* Cuando se requiera un job programado o daemon.

## 🛠️ How to use it (Flujo de Creación)

El agente debe seguir estos pasos en orden secuencial.

---

### Paso 1: Definición (Input)

Pregunta al usuario:

1. **Nombre del servicio:** (ej: `email-importer`, `stock-sync`)
   - Debe ser `kebab-case`
2. **Propósito:** Breve descripción de lo que hará

---

### Paso 2: Generación del Código Base

1. Crea el archivo `workers/<nombre_servicio>.py` con estructura básica:

```python
"""
Worker: <nombre_servicio>
Descripción: <propósito>
"""
import signal
import sys
import time
from services.logging import ctx_logger

logger = ctx_logger.get(__name__)

# Flag para graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    logger.info(f"Señal {signum} recibida, iniciando shutdown...")
    shutdown_requested = True

def main():
    """Loop principal del worker."""
    logger.info("Worker <nombre_servicio> iniciado")
    
    # Registrar handlers de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while not shutdown_requested:
        try:
            # TODO: Implementar lógica del worker
            time.sleep(10)
        except Exception as e:
            logger.error(f"Error en loop principal: {e}")
            time.sleep(5)
    
    logger.info("Worker <nombre_servicio> finalizado")

if __name__ == "__main__":
    main()
```

> [!IMPORTANT]
> Asegúrate de usar `services.logging.ctx_logger` para logs consistentes con el resto del sistema.

---

### Paso 3: Scripts de Arranque (Launchers)

Genera los scripts en `scripts/` para compatibilidad con el Job Manager:

#### Windows (`.cmd`)
Archivo: `scripts/start_worker_<nombre_servicio>.cmd`
```cmd
@echo off
python -m workers.<nombre_servicio>
```

#### Linux/Mac (`.sh`)
Archivo: `scripts/start_worker_<nombre_servicio>.sh`
```bash
#!/bin/bash
python -m workers.<nombre_servicio>
```

> [!TIP]
> En Linux/Mac, dar permisos de ejecución: `chmod +x scripts/start_worker_<nombre_servicio>.sh`

---

### Paso 4: Configuración Docker (Hot-Reload) 🔥

Edita `docker-compose.yml` agregando el nuevo servicio:

```yaml
worker-<nombre_servicio>:
  build:
    context: .
    dockerfile: infra/Dockerfile.dramatiq
  container_name: growen-worker-<nombre_servicio>
  command: watchmedo auto-restart --directory=./ --pattern=*.py --recursive -- python -m workers.<nombre_servicio>
  volumes:
    - ./:/app
  env_file:
    - .env
  depends_on:
    - db
  restart: unless-stopped
```

| Configuración | Descripción |
|---------------|-------------|
| `watchmedo auto-restart` | Reinicia automáticamente al detectar cambios en archivos `.py` |
| `--recursive` | Observa subdirectorios también |
| `volumes: ./:/app` | Monta el código local para hot-reload |

---

### Paso 5: Registro en Job Manager (Frontend Link) 🔗

Edita `services/jobs/manager.py`:

1. Busca el diccionario/lista donde se definen los servicios disponibles
2. Agrega una nueva entrada siguiendo el patrón existente:

```python
{
    "name": "<nombre_servicio>",
    "display_name": "<Nombre Legible>",
    "script_windows": "scripts/start_worker_<nombre_servicio>.cmd",
    "script_unix": "scripts/start_worker_<nombre_servicio>.sh",
    "description": "<propósito>",
}
```

> [!NOTE]
> El registro en el Job Manager hace que el servicio aparezca automáticamente en el Panel de Servicios del Admin (`ServicesPanel.tsx`).

---

## ✅ Validación Final

Checklist para el agente:

| Verificación | Acción |
|--------------|--------|
| ✅ Worker creado | `workers/<nombre>.py` existe |
| ✅ Scripts generados | `.cmd` y `.sh` en `scripts/` |
| ✅ Docker configurado | Entrada en `docker-compose.yml` |
| ✅ Job Manager actualizado | Entrada en `services/jobs/manager.py` |

**Informa al usuario:**
1. Reiniciar Docker: `docker compose up -d --build`
2. El servicio aparecerá en el Panel Admin automáticamente
3. Hot-reload activo: los cambios en código reiniciarán el worker automáticamente

---

## 💡 Comandos Útiles

| Acción | Comando |
|:-------|:--------|
| Ver logs del worker | `docker logs -f growen-worker-<nombre>` |
| Reiniciar worker | `docker compose restart worker-<nombre>` |
| Detener worker | `docker compose stop worker-<nombre>` |
| Ejecutar localmente | `python -m workers.<nombre>` |
