<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SIYUAN_MCP_20260828.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_SIYUAN_MCP_20260828.md -->
<!-- NG-HEADER: Descripción: Retrospectiva de edición segura y bases estructuradas de SiYuan mediante MCP. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva: SiYuan MCP — 2026-08-28

## Contexto

La sesión implementó edición segura de documentación en el notebook `Nice Grow`
y una mutación estructurada de tareas sobre un documento privado autorizado. La
evidencia disponible comprende el diff local, pruebas focales, validación de
Compose, catálogo MCP del contenedor, respuestas semánticas de SiYuan y revisión
visual en Chrome. No se realizó commit ni push; el trabajo permaneció en `dev`.

El worktree ya contenía cambios ajenos en documentación, frontend y scripts de
calidad. Se conservaron y no se atribuyen a esta entrega.

## Observaciones

| Tarea | Estado | Evidencia |
|---|---|---|
| Separar `/Growen` de las raíces privadas | Completada | Políticas por rol, pruebas de catálogo y 68 pruebas focales aprobadas. |
| Leer y actualizar documentos privados con revisión | Completada | SHA-256, historial previo, conflicto optimista y estados inciertos cubiertos. |
| Sincronizar Git → SiYuan sin borrar | Completada | Estado externo, adopción, conflictos, forzado explícito y huérfanos probados. |
| Crear una base `Tareas` por MCP | Completada | Invocación STDIO real, API semántica y comprobación visual en SiYuan 3.8.1. |
| Automatizar el smoke estructurado en el gate general | Parcial | Existe script invocable; falta integrarlo a un workspace desechable automatizado. |

La documentación de MCP, seguridad, roles, pruebas, configuración, README,
Roadmap y changelog quedó alineada con las seis tools administrativas y las tres
tools visibles para colaboradores.

## Errores y/u outputs

1. SiYuan 3.8.1 agregó una columna vacía `Select` al crear la Attribute View.
   La causa quedó confirmada mediante lectura semántica y observación visual. La
   reejecución de la tool ahora reconcilia exclusivamente esa columna generada y
   vacía, sin duplicar la base ni afectar datos del usuario.
2. Recrear el servicio MCP mediante Compose también recreó su dependencia
   SiYuan. Ambos servicios recuperaron estado saludable; el riesgo residual es
   que un smoke contra un workspace no desechable interrumpa brevemente la UI.
3. La primera ejecución del nuevo test agéntico fue bloqueada por permisos del
   sandbox. Al ejecutarlo con el venv autorizado, el RED falló por la referencia
   ausente y el GREEN aprobó. Una aserción intermedia sensible a mayúsculas se
   normalizó para comprobar contenido y no estilo tipográfico.
4. La suite focal terminó con `68 passed` y una advertencia deprecada de
   Starlette/httpx. No afectó el resultado, pero continúa como deuda de entorno.
   El cierre consolidó esa suite con los contratos agénticos: `73 passed` y la
   misma advertencia, sin fallos.

## Objetivo

Preservar un procedimiento repetible para que futuras tools SiYuan mantengan la
frontera de autoridad, no confundan Markdown con estructuras Attribute View y
se acepten con evidencia del protocolo, del estado persistido y de la interfaz.

## Propuesta de código o pasos

### Prevención

- **Aplicada — ampliar `create-service`:** evidencia: la columna `Select` y la
  diferencia entre Markdown y Attribute View requirieron reconciliación. Uso
  esperado: cada nueva mutación SiYuan. Beneficio alto, mantenimiento bajo. La
  referencia canónica exige historial, no reintento, estado incierto y validación
  de autoridad antes de escribir.
- **Pendiente — workspace desechable:** evidencia: Compose recreó SiYuan durante
  el smoke. Uso esperado: poco frecuente pero de alto impacto. Beneficio alto,
  costo medio. Incorporar un fixture aislado antes de automatizar el smoke.

### Aceleración

- **Aplicada — contrato de aceptación en tres capas:** evidencia: MCP, API y
  Chrome detectaron problemas diferentes. Uso esperado: toda tool estructurada.
  Beneficio alto, mantenimiento bajo. La guía está en
  `.agents/skills/create-service/references/siyuan-mcp-mutations.md` y cuenta con
  una prueba contractual.
- **Pendiente — parametrizar el script de smoke:** beneficio medio, costo bajo.
  Permitir seleccionar documento desechable y versión esperada sin incorporar
  contenido privado al repositorio.

## Criterios de aceptación

- Las tareas se clasifican sólo con evidencia disponible y se separan de los
  cambios preexistentes del worktree.
- Los incidentes incluyen causa o límite explícito, solución, validación y riesgo
  residual sin registrar contenido privado ni secretos.
- La mejora agéntica está materializada, documentada y cubierta por una prueba.
- README, Roadmap y documentación afectada reflejan el comportamiento vigente.
- Los pendientes no se presentan como completados y toda referencia
  desactualizada verificable se actualiza.
