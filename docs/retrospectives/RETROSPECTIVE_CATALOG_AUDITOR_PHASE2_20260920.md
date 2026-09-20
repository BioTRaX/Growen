<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_CATALOG_AUDITOR_PHASE2_20260920.md -->
<!-- NG-HEADER: Ubicación: docs/retrospectives/RETROSPECTIVE_CATALOG_AUDITOR_PHASE2_20260920.md -->
<!-- NG-HEADER: Descripción: Retrospectiva del piloto integral y resolución supervisada del auditor de catálogo. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva: auditor de catálogo Fase 2 — 2026-09-20

## Contexto

La sesión recuperó el piloto integral del auditor autónomo, estabilizó su
ejecución con Enrich, MCP Web Search y Ollama, añadió identidad y navegación
seguras en Vue y habilitó la aceptación administrativa supervisada desde
Productos. El alcance incluyó backend, worker, contratos Vue, pruebas,
documentación y verificación local autenticada.

El trabajo partió de un `HEAD` separado basado en `dev` y contenía todos los
cambios acumulados de la fase. Durante el cierre se creó la rama efímera
`feat/cierre-auditor-catalogo-fase-2`; no se atribuyen al estado productivo los
resultados locales ni los manifiestos versionados.

## Observaciones

| Tarea | Estado | Evidencia |
|---|---|---|
| Ejecutar los 29 canónicos | Completada | Run real sin fallos técnicos y repetición estable con reutilización de los 29 resultados. |
| Recuperar fallos de Enrich y JSON | Completada | Reintentos diferenciados, `review_required` preservado e invalid JSON cerrado tras un retry. |
| Identificar y navegar productos | Completada | Los 29 nombres y enlaces internos se recorrieron con sesión admin. |
| Aceptar revisión supervisada | Completada | Admin dispone de acción con nota; colaborador no la ve y recibe `403` por API. |
| Resolver los 10 hallazgos | Completada | PostgreSQL confirmó 29 `clean`, 10 excepciones activas y 10 `accept_exception`. |
| Relanzar una corrida por clic | Diferida | El usuario indicó reauditar cuando existan productos nuevos. |

## Errores y/u outputs

1. **JWT de MCP Web Search rechazado.** La audiencia usaba un secreto distinto
   del consumidor. Se alineó con `MCP_WEB_SEARCH_SECRET_KEY` y se preservó la
   compatibilidad de rotación sin registrar valores.
2. **Runs reanudados retenían un job Enrich terminal.** Se limpió la referencia,
   se recalcularon contadores y se incorporó el intento persistido a la clave
   idempotente.
3. **Respuesta Ollama no JSON.** Se añadió un único retry y fallo cerrado si la
   segunda respuesta continúa inválida.
4. **Snapshots con `Decimal` producían HTTP 500 al persistir JSONB.** Se
   normalizaron a texto exacto y se verificaron corrección, restauración y
   reauditoría trazadas.
5. **IDs canónicos usados como rutas de producto.** El backend ahora resuelve en
   lote el `Product.id` interno y Vue omite el enlace cuando no existe ficha.
6. **Primer diagnóstico PostgreSQL apuntó a `localhost:5432`.** Compose publicaba
   el servicio healthy en `127.0.0.1:5433`. La verificación final se ejecutó con
   `psql` dentro del contenedor, en lectura y sin imprimir credenciales.
7. **Suite Vue bajo carga paralela agotó dos timeouts.** Ambos casos aprobaron
   aislados y la suite completa aprobó al repetirse sin competencia de CPU.
8. **Ruff del router monolítico.** El gate encontró 15 hallazgos heredados en
   `services/routers/catalog.py`. Como el archivo estaba dentro del alcance y la
   publicación exige Ruff limpio, se eliminaron imports y variables muertos y
   se hicieron explícitas comparaciones SQLAlchemy semánticamente equivalentes;
   Ruff y la regresión focal aprobaron después del saneamiento.
9. **Revisión independiente sin dictamen.** El agente revisor agotó su cuota
   antes de responder y no modificó el árbol. Se conservó el bloqueo hasta
   completar una revisión manual del diff y repetir las compuertas sobre el
   árbol exacto que se integraría.

Riesgos residuales: el estado local no verifica producción; el worker Enrich
mantiene una deuda separada de cierre tardío de clientes async; una futura
corrida puede producir nuevos hallazgos cuando cambie el catálogo o las reglas.

## Objetivo

Cerrar la fase con decisiones humanas trazables, sin convertir recomendaciones
de IA en cambios automáticos y sin confundir evidencia local con despliegue
productivo.

## Propuesta de código o pasos

### Prevención

- Conservar la separación entre `needs_review`, excepción aceptada y corrección
  aplicada; toda resolución debe llevar actor y nota.
- Reauditar desde Vue cuando ingresen productos nuevos y verificar nuevamente
  API, broker, worker y PostgreSQL antes de afirmar un resultado integral.
- Mantener Ruff focal sobre todo router tocado para no volver a acumular deuda
  histórica invisible tras una suite funcional verde.

### Evolución agéntica

Se probó un escenario de control sin ampliar `diagnose-local-services`: ante un
PostgreSQL publicado en un puerto no estándar y sin contraseña en el proceso,
el agente eligió correctamente `psql` dentro del contenedor, lectura acotada y
salida sin secretos. Como la conducta ya estaba cubierta por la skill vigente,
no se agregó una regla redundante. El gate agéntico sí reveló que
`check-quality.ps1` asumía una `.venv` dentro de cada worktree; se incorporó el
parámetro opcional `-PythonPath` para reutilizar el intérprete canónico sin
duplicar entornos. La mejora se validó ejecutando `-AgentOnly` desde este
worktree. También se corrigieron enlaces relativos rotos en
`docs/development/AGENT_SKILLS.md`.

## Estado operativo

- PostgreSQL y Redis locales permanecían activos en Compose al cierre;
  PostgreSQL estaba publicado en `127.0.0.1:5433` y Redis en loopback 6379.
- API y Vue locales permanecían escuchando en 8000 y 5176 respectivamente.
- Los procesos aislados usados por el smoke en 8001 y 5177 fueron detenidos.
- Los usuarios sintéticos del smoke fueron eliminados.
- No se modificaron secretos, certificados, volúmenes ni servicios externos.
- No se repitió el despliegue productivo ni se afirma su estado actual.

## Criterios de aceptación

- Los resultados funcionales están respaldados por pruebas, smoke autenticado
  y consultas persistentes de sólo lectura.
- Los 10 hallazgos tienen decisión humana y los 29 canónicos quedan `clean`.
- No se aplicaron recomendaciones de IA automáticamente ni se expusieron
  secretos.
- La evolución agéntica evita duplicar una skill cuyo escenario de control ya
  aprobó.
- README, Roadmap, changelog y documentos de dominio quedan actualizados; todo
  contenido desactualizado encontrado se corrige o se registra como deuda.
