# [Contexto]
# Soy un desarrollador trabajando en el proyecto "Growen", que se orquesta con el archivo `docker-compose.yml` en la raíz de mi proyecto.
# Después de una limpieza, necesito asegurarme de que mi entorno de desarrollo esté completo, actualizado y listo para funcionar.
# Mi `docker-compose.yml` contiene tanto imágenes personalizadas que se construyen localmente (como 'api', 'frontend') como imágenes base públicas (como 'alpine').
# Mi objetivo es crear un script de PowerShell que audite y prepare mi entorno de forma inteligente.

# [Objetivo]
# Generar un script de PowerShell que realice las siguientes tareas en orden:
# 1.  **Verificar Entorno:** El script debe comprobar que el archivo `docker-compose.yml` exista en el directorio actual. Si no, debe detenerse.
# 2.  **Leer y Analizar:** Cargar el contenido del `docker-compose.yml` para analizar los servicios.
# 3.  **Auditar Imágenes Públicas:**
#     - Identificar los servicios que usan imágenes públicas (ej: `pdf_import` usa `alpine:3.19`). Ignorar los servicios que tienen una sección `build`, ya que son locales.
#     - Para cada imagen pública, conectarse a la API de Docker Hub para buscar los tags de versión disponibles.
#     - Filtrar los tags para encontrar la última versión ESTABLE. La lógica debe ignorar tags como `latest`, `edge`, `rc`, `beta` y priorizar el versionado semántico numérico más alto (ej: `3.20.1` es preferible a `3.19`).
#     - Mostrar al usuario una tabla comparativa clara. Ejemplo:
#       "Servicio 'pdf_import' usa 'alpine:3.19'. Última versión estable encontrada: '3.20.1'. ¿Actualizar?"
# 4.  **Confirmación de Actualización (Opcional):**
#     - Preguntar al usuario si desea crear una copia del `docker-compose.yml` con las versiones de las imágenes públicas actualizadas.
#     - Si el usuario confirma, crear un backup (`docker-compose.yml.bak`) y guardar el nuevo archivo con los tags actualizados. Si no, continuar con el archivo actual.
# 5.  **Construir y Levantar el Stack:**
#     - Ejecutar el comando `docker-compose up --build -d`. El flag `--build` es crucial para reconstruir las imágenes locales como `api` y `frontend` que podrían haberse eliminado.
#     - El flag `-d` lo dejará corriendo en segundo plano.
# 6.  **Verificación Final:** Una vez levantado, ejecutar `docker-compose ps` para mostrar una tabla con el estado actual de todos los contenedores y confirmar que estén corriendo (`Up`).

# [Criterios de Aceptación]
# - El script debe ser interactivo y pedir confirmación antes de modificar el `docker-compose.yml`.
# - La lógica para diferenciar entre imágenes locales (con `build`) y públicas (sin `build`) es fundamental.
# - El output debe ser claro y guiarme en cada paso.
# - Debe incluir manejo de errores básico, por si `docker-compose` no está instalado o falla.