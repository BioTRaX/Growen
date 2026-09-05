<!-- NG-HEADER: Nombre de archivo: README.md -->
<!-- NG-HEADER: Ubicación: siyuan-widgets/crono/README.md -->
<!-- NG-HEADER: Descripción: Uso, contrato de datos y pruebas del widget Crono para SiYuan. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Widget Crono para SiYuan

Crono muestra como tarjetas las filas pendientes de una Attribute View y permite
medir el tiempo de cada tarea. Al detener el contador, persiste el total
normalizado en `Minutos` y `Segundos`, marca el primer campo de tipo checkbox y
recarga la vista para ocultar la tarjeta completada. La columna `Estado` refleja
si la tarea todavía no comenzó, está activa o ya terminó.

## Contrato de la Attribute View

- `Minutos`: columna `Number` obligatoria.
- `Segundos`: columna `Number` obligatoria.
- `Estado`: columna `Select` obligatoria.
- `Categoria`: columna `Select` opcional y de sólo lectura.
- Una columna de tipo `Checkbox` para completar la tarea.
- Una columna de tipo `Block` usada como nombre de la tarjeta.

Los nombres `Minutos` y `Segundos` no distinguen mayúsculas de minúsculas. Si el
widget se detiene antes de completar un minuto, guarda `0` en `Minutos` y los
segundos transcurridos en `Segundos`. Las ejecuciones se suman al valor previo y
se normalizan, por ejemplo `1 min 59 s + 2 s = 2 min 1 s`.

El estado se reconcilia al cargar y en cada acción:

- `Sin iniciar`: no existe un cronómetro activo y el checkbox está desmarcado.
- `Iniciada`: existe un cronómetro activo, incluso después de recargar SiYuan.
- `Completada`: el tiempo terminó y el checkbox quedó marcado.

Al detener una tarea, Crono guarda minutos, segundos y `Completada` antes de
marcar el checkbox. Si alguna escritura falla, la tarjeta permanece visible.

Cuando existe `Categoria`, sus valores se muestran como etiquetas centradas en
la tarjeta. Cada etiqueta conserva el código de color configurado en SiYuan;
Crono nunca escribe ni normaliza esta columna.

La comparación visual de esta versión cubre los códigos usados por la tabla de
prueba: `1` rojo, `2` amarillo y `3` azul. Los demás códigos conservan una
paleta diferenciada local, pero requieren validación visual cuando aparezcan en
datos reales.

## Sincronización operativa

Comparar la fuente con el workspace activo, sin escribir:

```powershell
.\scripts\sync-siyuan-widget.ps1 -WidgetName crono
```

Después de revisar el drift y contar con autorización para sobrescribir los
archivos runtime:

```powershell
.\scripts\sync-siyuan-widget.ps1 -WidgetName crono -Apply
```

El script no copia `README.md` ni `tests/`, no elimina archivos extras y no lee
tokens de SiYuan.

## Prueba de regresión

Desde la raíz del repositorio:

```powershell
node --test siyuan-widgets/crono/tests/crono-core.test.cjs
```
