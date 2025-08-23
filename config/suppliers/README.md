# Mapeos de proveedores

Cada archivo `.yml` describe cómo convertir las columnas de un archivo de un proveedor en los campos internos de Growen. El módulo `services.suppliers.parsers` genera un `GenericExcelParser` por cada YAML encontrado.
Para crear uno nuevo, copie `default.yml` y ajuste los nombres de columnas y transformaciones. El nombre del archivo se usa como `slug` salvo que se defina explícitamente en el YAML.

Si se requiere un parser más complejo, pueden instalarse paquetes que
exponan un `entry_point` en el grupo `growen.suppliers.parsers`. Las
instancias detectadas se combinan automáticamente con las declaradas por
YAML.

Campos principales:
- `file_type`: `csv` o `xlsx`.
- `columns`: listas de posibles encabezados por campo interno.
- `transform`: reglas de limpieza (ej. `replace_comma_decimal`).
- `defaults`: valores por defecto como `status` o `stock_qty`.
