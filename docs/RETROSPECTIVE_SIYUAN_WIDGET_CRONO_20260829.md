<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SIYUAN_WIDGET_CRONO_20260829.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_SIYUAN_WIDGET_CRONO_20260829.md -->
<!-- NG-HEADER: Descripción: Retrospectiva del widget Crono y mejoras agénticas derivadas. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva: widget Crono de SiYuan — 2026-08-29

## Contexto

La sesión corrigió y amplió el widget `siyuan-widgets/crono`: persistencia de
minutos y segundos, estados `Sin iniciar`, `Iniciada` y `Completada`, y
categorías centradas de sólo lectura. La evidencia comprende código, ciclo TDD,
respuestas de la API Attribute View, hashes de la copia operativa, consola y
capturas de Chrome sobre SiYuan 3.8.1.

El worktree ya contenía numerosos cambios ajenos en backend, frontend,
migraciones, MCP y documentación. Se preservaron y no se atribuyen a esta
sesión. Las mutaciones externas propias fueron los smokes sobre `afgg` y
`Tarea 3`; esta última terminó `Completada`, con `0 min 42 s`, checkbox marcado
y categoría `Personal` color `2`. No se realizó commit ni push.

## Observaciones

| Tarea | Estado | Evidencia |
|---|---|---|
| Persistir minutos y segundos | Completada | Pruebas Node y smoke de 2 s guardaron ambas columnas antes del checkbox. |
| Reconciliar el ciclo de estados | Completada | API confirmó `Iniciada` durante Play y `Completada` después de Stop. |
| Mostrar categorías sin escribirlas | Completada | Chrome mostró etiquetas centradas y la API conservó `Personal`, color `2`. |
| Versionar y documentar Crono | Completada | Excepción acotada en `.gitignore`, README, Roadmap y changelog actualizados. |
| Automatizar el smoke desechable | Parcial | Existe sincronizador probado; falta un workspace efímero con Attribute View. |

## Errores y/u outputs

1. **Tiempo perdido bajo 60 segundos.** La causa confirmada era el guardado
   condicionado a `elapsedMinutes > 0` y la ausencia total de `Segundos`. Se
   reemplazó por acumulación en segundos totales y normalización; el RED falló y
   el GREEN aprobó.
2. **Fuente distinta del runtime.** SiYuan servía
   `../growen-siyuan/workspace/data/widgets/crono`, no la copia versionada. Se
   compararon hashes y se sincronizaron archivos acotados. El nuevo script hace
   este control repetible y es de sólo lectura por defecto.
3. **Contrato heterogéneo de Attribute Views.** `Number` y `Checkbox` usan un
   envoltorio por tipo; `Select` exige `type` y `mSelect`. Se aisló la
   serialización y se cubrió con pruebas.
4. **Locator ambiguo en Chrome.** Un selector de Play resolvió dos tarjetas. Se
   acotó primero el `li` por nombre y luego el botón, evitando clicks sobre una
   tarea equivocada.
5. **Paleta inicialmente incorrecta.** La primera captura mostró que los códigos
   `1`, `2` y `3` no coincidían con SiYuan. Se corrigieron a rojo, amarillo y
   azul y se repitió el control visual. Los códigos `4–13` no fueron observados.
6. **API bloqueada sin autenticación.** Una lectura directa devolvió el bloqueo
   de pantalla. La verificación posterior usó el token local desde archivo sólo
   como header hacia loopback, sin imprimirlo ni persistirlo.
7. **`Get-FileHash` ausente bajo pytest.** El sincronizador funcionaba en una
   consola normal, pero el subproceso de prueba no cargó ese cmdlet. Se cambió a
   SHA-256 de .NET.
8. **`$PSScriptRoot` vacío en valores predeterminados.** La invocación real
   reveló que resolver las raíces dentro de la declaración `param` no era
   estable en todos los hosts. La resolución se movió al cuerpo del script y se
   agregó una regresión que invoca únicamente `-WidgetName`; el conjunto focal
   terminó con `2 passed`.

Riesgos residuales: las escrituras de tiempo, estado y checkbox no son
transaccionales; un fallo intermedio puede dejar una actualización parcial. El
cronómetro también reside en `localStorage`, por lo que otro navegador no puede
recuperarlo. La equivalencia visual de colores sólo está comprobada para `1–3`.

## Objetivo

Preservar un flujo repetible que distinga cálculo puro, contrato Attribute View,
copia operativa y evidencia visual, sin convertir pasos mecánicos en una skill
redundante ni exponer secretos o contenido privado.

## Propuesta de código o pasos

### Prevención

- **Aplicada — TDD del contrato:** evidencia: el umbral de 60 segundos y el
  payload `Select` fallaban de formas distintas. Frecuencia alta en futuras
  columnas. Beneficio alto, mantenimiento bajo. Conservar funciones puras y
  probar payloads antes de tocar la instancia real.
- **Aplicada — sincronización segura:** evidencia: fuente y runtime estaban en
  raíces distintas. Frecuencia alta por cada cambio del widget. Beneficio alto,
  costo bajo. Usar `sync-siyuan-widget.ps1` sin `-Apply` primero.
- **Pendiente — recuperación de parciales:** beneficio alto, costo medio.
  Diseñar una operación idempotente o estado intermedio antes de ampliar Crono.

### Aceleración

- **Aplicada — script determinista en lugar de skill:** el escenario base sin
  skill ya produjo un procedimiento correcto, por lo que una skill nueva no
  aportaba conducta. El script elimina la comparación y copia manual repetida.
- **Pendiente — workspace efímero de widgets:** frecuencia media, beneficio
  alto, costo medio. Debe crear una Attribute View desechable, ejecutar Play y
  Stop y comprobar persistencia sin modificar tareas privadas.

## Criterios de aceptación

- Cada resultado se apoya en pruebas, API, hashes o evidencia visual disponible.
- Los cambios propios y las mutaciones externas se separan del worktree previo.
- Los incidentes registran causa, solución, validación y riesgo residual sin
  secretos.
- La mejora agéntica está materializada en un script probado y documentado.
- README, Roadmap, changelog, `AGENTS.md`, testing y documentación agéntica están
  actualizados; los pendientes no se presentan como completados.
