# Mapeos de proveedores

Cada archivo `.yml` describe cómo convertir las columnas de un archivo de un proveedor en los campos internos de Growen. Para crear uno nuevo, copie `default.yml` y ajuste los nombres de columnas y transformaciones.

Campos principales:
- `file_type`: `csv` o `xlsx`.
- `columns`: listas de posibles encabezados por campo interno.
- `transform`: reglas de limpieza (ej. `replace_comma_decimal`).
- `defaults`: valores por defecto como `status` o `stock_qty`.
