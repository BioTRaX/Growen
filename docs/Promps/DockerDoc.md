# [Rol y Contexto]
# Actúa como un ingeniero experto en DevOps y seguridad de contenedores.
# Estoy trabajando en un proyecto multi-servicio con Docker Compose y mi objetivo es optimizar y asegurar cada uno de mis Dockerfiles.
# A continuación, te proporcionaré el contenido de un Dockerfile específico de mi proyecto para que lo analices y lo reescribas aplicando las mejores prácticas.
# Mis prioridades son:
# 1.  **Seguridad:** Minimizar la superficie de ataque y eliminar vulnerabilidades conocidas.
# 2.  **Eficiencia:** Reducir el tamaño final de la imagen.
# 3.  **Rendimiento:** Acelerar el proceso de construcción (build).
# 4.  **Confiabilidad:** Asegurar que los builds sean reproducibles y consistentes.

# [Objetivo Detallado]
# Analiza el Dockerfile que te proporcionaré y realiza las siguientes acciones:

# 1.  **Analizar la Imagen Base (`FROM`):**
#     -   Identifica la imagen base y su versión.
#     -   Busca en Docker Hub si existe una versión estable más reciente o una variante más recomendada (priorizando `alpine` o `slim` si es aplicable).
#     -   Actualiza la línea `FROM` a la versión específica y recomendada (ej: `python:3.12-slim-bookworm` o `node:22-alpine`), evitando tags flotantes como `latest`.

# 2.  **Gestionar Dependencias del Sistema:**
#     -   Basado en el tipo de aplicación (Python, Node.js, etc.) y los archivos de dependencias (`requirements.txt`, `package.json`), determina qué librerías de sistema son necesarias para la compilación o ejecución.
#     -   Para Python (si ves paquetes como `psycopg`, `opencv-python`, `weasyprint`): Agrega un `RUN apt-get install` (para Debian) o `RUN apk add` (para Alpine) con las dependencias necesarias (ej: `build-essential`, `libpq-dev`, `tesseract-ocr`, etc.).
#     -   Para Node.js: Si se necesitan herramientas de compilación, agrega los paquetes correspondientes (ej: `build-base` en Alpine).
#     -   Asegúrate de limpiar la caché del gestor de paquetes en la misma capa `RUN` para reducir el tamaño (ej: `&& rm -rf /var/lib/apt/lists/*` o usando `--no-cache` en `apk`).

# 3.  **Implementar Builds Multi-Etapa (Multi-Stage Builds):**
#     -   Si el Dockerfile es para una aplicación que se compila (como un frontend de Vite/React) o que tiene dependencias de build pesadas (como Python con `pandas` y `opencv`), reestructura el archivo para usar un build multi-etapa.
#     -   La primera etapa (`AS builder`) debe contener todas las herramientas de desarrollo y construir el artefacto de producción (ej: la carpeta `dist` del frontend o las ruedas de Python).
#     -   La etapa final debe partir de una imagen mínima (ej: `nginx:stable-alpine` o una imagen `distroless`) y copiar únicamente los artefactos construidos desde la etapa `builder`.

# 4.  **Optimizar el Cacheo de Capas:**
#     -   Estructura las instrucciones `COPY` y `RUN` para maximizar el uso del caché de Docker.
#     -   Copia primero solo los archivos de manifiesto de dependencias (`requirements.txt`, `package.json`, `package-lock.json`).
#     -   Ejecuta la instalación de dependencias (`pip install`, `npm ci`).
#     -   Copia el resto del código fuente de la aplicación DESPUÉS de instalar las dependencias.

# 5.  **Aplicar Buenas Prácticas Generales:**
#     -   Para Python, actualiza `pip` y `setuptools` antes de instalar los `requirements.txt`.
#     -   Usa `--no-cache-dir` con `pip` y `npm ci` en lugar de `npm install`.
#     -   Asegúrate de que el `Dockerfile` esté completamente comentado, explicando la razón de cada paso importante.

# [Inicio del Análisis]
# A continuación, te presento el Dockerfile que quiero que optimices:

# [AQUÍ PEGAS EL CONTENIDO DE TU DOCKERFILE ACTUAL]