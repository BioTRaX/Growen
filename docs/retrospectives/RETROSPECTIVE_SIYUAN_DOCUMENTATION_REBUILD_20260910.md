<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SIYUAN_DOCUMENTATION_REBUILD_20260910.md -->
<!-- NG-HEADER: Ubicación: docs/retrospectives/RETROSPECTIVE_SIYUAN_DOCUMENTATION_REBUILD_20260910.md -->
<!-- NG-HEADER: Descripción: Retrospectiva de la reconstrucción de documentación Git en SiYuan y la mejora de coordinación agéntica. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva: reconstrucción de documentación Git en SiYuan

## Contexto

La reorganización versionada de la documentación no se había replicado en
`/Growen/Documentación técnica`. Git se confirmó como única fuente de verdad y
se autorizó reconstruir exclusivamente esa raíz, sin conservar ediciones
manuales ni crear un snapshot previo.

## Observaciones

- El catálogo publicado comprende los Markdown versionados de la raíz y
  `docs/**/*.md`, incluyendo archivos archivados, planes y retrospectivas.
- `/Growen/Pruebas MCP`, `/Negocio` y `/Operación` quedaron fuera del alcance
  destructivo.
- El estado externo no tenía baseline previo; la reconstrucción debía registrar
  SHA Git, fase, ID eliminado, hashes y checkpoints sin contenido ni secretos.
- El repositorio usa un único checkout físico compartido. Durante esta sesión
  otro agente ocupó la rama inicialmente, lo que confirmó que el cambio de rama
  también requiere coordinación explícita y no sólo locks por archivo.

## Errores y outputs relevantes

- El diagnóstico inicial mostró 129 documentos gobernados, 81 creaciones, seis
  conflictos y ninguna categoría nueva reflejada en SiYuan.
- `removeDocByID` agotó el timeout aunque el borrado sí se aplicó. La respuesta
  de transporte no representaba de forma concluyente el estado remoto.
- Después de crear documentos, SiYuan demoró su disponibilidad de lectura. Un
  checkpoint inmediato podía registrar como fallida una escritura ya aceptada.
- La primera reanudación encontró la fase `deleting` y documentos ya recreados,
  pero sin baseline completo.

## Implementación y solución

- El publicador descubre el catálogo con Git, exige Markdown limpio, ejecuta el
  control de secretos y limita `--rebuild` a una confirmación literal de
  `/Growen/Documentación técnica`.
- El borrado interno valida ruta e ID, y reconcilia respuestas inciertas mediante
  una lectura posterior. La fase persistida permite pasar de `deleting` a
  `recreating` y reanudar sin repetir el borrado.
- Cada creación espera hasta que el documento sea legible antes de confirmar su
  checkpoint. El baseline se actualiza de forma incremental y nunca almacena
  contenido.
- Como evolución agéntica, `scripts/agent_lock.py` incorpora `renew` y se adopta
  el ámbito global `git-worktree` para serializar cambios de rama durante toda
  una tarea. La migración a un worktree por agente queda como decisión futura.

## Evidencia de validación

- La reconstrucción real creó y checkpointó 129 documentos; el dry-run
  inmediatamente posterior informó 129 elementos `unchanged`.
- El estado externo quedó en fase `complete` con el SHA publicado y 129 hashes.
- La huella de los siete documentos protegidos fue idéntica antes y después de
  la reconstrucción.
- Un workspace SiYuan desechable confirmó borrado recursivo de raíz y
  descendientes, preservando un documento hermano.
- La suite focal del publicador, Ruff, el gate agéntico, el control de calidad y
  las pruebas del coordinador de locks se ejecutan nuevamente antes del cierre.

## Estado operativo persistente y riesgo residual

- La réplica real de SiYuan y el baseline externo sí fueron modificados. No se
  desplegaron contenedores, certificados, volúmenes ni secretos productivos; el
  contenedor descartable fue removido.
- Una indisponibilidad prolongada de SiYuan puede dejar una operación con estado
  incierto. La recuperación prevista es releer la raíz y reanudar con `--apply`,
  nunca repetir automáticamente un borrado ambiguo.
- Los locks siguen siendo cooperativos: un cliente que ignore `AGENTS.md` puede
  escribir sobre el checkout. El aislamiento físico mediante `git worktree add`
  continúa pendiente hasta definir rutas, puertos y autoridad del checkout
  central.

## Criterios de aceptación

- El catálogo final coincide exactamente con el conjunto Git del SHA publicado.
- El dry-run final sólo informa documentos sin cambios, sin conflictos,
  huérfanos ni operaciones pendientes.
- Las raíces protegidas conservan su identidad y contenido.
- Las pruebas de reconstrucción, reanudación y locks renovables finalizan sin
  fallos.
- Los cambios quedan documentados y se actualiza cualquier documentación
  desactualizada.
