# Growen

Agente modular para cultivo y e-commerce.

## Configuración de Base de Datos

1. Crea un archivo `.env` basado en `.env.example` y ajusta las credenciales.
2. Instala las dependencias del proyecto:
   ```bash
   pip install -e .[dev]
   ```
3. Ejecuta las migraciones para crear las tablas:
   ```bash
   python -m cli.ng db init
   ```
4. Verifica la cantidad de registros:
   ```bash
   python -m cli.ng db info
   ```
5. Exporta el catálogo a CSV:
   ```bash
   python -m cli.ng catalog export --out catalogo.csv
   ```
6. Corre los tests:
   ```bash
   pytest
   ```

## Ejecución del servicio API

1. Inicia el backend de desarrollo:
   ```bash
   uvicorn services.api:app --reload
   ```
2. Revisa la salud del servicio visitando `http://localhost:8000/health`.
