<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SESSION_20260919.md -->
<!-- NG-HEADER: Ubicación: docs/retrospectives/RETROSPECTIVE_SESSION_20260919.md -->
<!-- NG-HEADER: Descripción: Retrospectiva del auditor completo y su integración con Productos Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — auditor de catálogo y Productos

## Contexto

La sesión continuó la Fase 2 sobre `feat/auditor-catalogo-completo`. Se
recuperó el procesamiento real de los 29 canónicos, se preservó la separación
entre Enrich y el auditor y se corrigió la experiencia para identificar y
resolver revisiones desde Vue.

## Resultados comprobados

- El piloto procesó 29 canónicos sin fallos técnicos: 19 resultados estables
  reutilizables y 10 `needs_review`, sin huérfanos ni cuarentenas.
- El detalle de una corrida expone nombre canónico y `Product.id` interno en
  consultas agrupadas. La UI no usa `CanonicalProduct.id` como ruta de ficha.
- Productos recibe las coordenadas del último ítem auditado sin consultas por
  fila y permite a admin aceptar una excepción con nota. El backend conserva
  estado `clean`, resolución y feedback; colaborador recibe 403.
- La reanudación descarta referencias a jobs Enrich terminales, recalcula los
  contadores y vuelve a encolar únicamente ítems fallidos o cancelados.
- Los snapshots de corrección/restauración serializan medidas decimales sin
  perder exactitud.

## Dificultades y decisiones

- El smoke visual no pudo ejecutarse: API y Vite rechazaron conexión en
  `127.0.0.1:8000` y `127.0.0.1:5176`. Se evitó reutilizar cookies o
  credenciales personales y no se declaró validación visual.
- Ruff focal encontró 15 incidencias históricas en el monolito
  `services/routers/catalog.py`, fuera de las líneas agregadas. Los demás
  archivos focales quedaron limpios; no se amplió el alcance con una limpieza
  masiva ni se agregaron supresiones.
- La prueba sin guidance para evolucionar `vue-module-migration` ya eligió el
  ID interno, rechazó el fallback canónico y pidió un contrato nullable. No se
  modificó la skill porque no existía una falla reproducible que justificarla.

## Evidencia de validación

- Backend focal: 15 pruebas aprobadas.
- Vue: 121 pruebas aprobadas en 40 archivos.
- `vue-tsc` y build Vite: código cero; 825 módulos transformados.
- Auditor documental, Ruff de archivos nuevos y `git diff --check`: código
  cero.
- El gate integral detectó `soupsieve 2.8.4`; se fijó el mínimo seguro en
  `2.9.0`, se regeneraron locks con hashes y se repitió la compuerta completa.
- La primera repetición alcanzó 61 pruebas backend y luego encontró referencias
  al frontend React retirado; se sanearon el gate, el workflow manual y Ruff.
- La repetición final del gate pasó: seguridad y SBOM, 61 pruebas backend, 121
  unitarias Vue, 6 E2E, typecheck, build y auditoría npm sin vulnerabilidades.
- Permanece el aviso conocido de compatibilidad TestClient/httpx, derivado a la
  fase de saneamiento.

## Estado operativo y riesgo residual

No se desplegaron servicios, no se modificaron volúmenes, secretos,
certificados ni infraestructura externa durante esta sesión. Los worktrees de
handoff parten del árbol vigente, pero deben aislar puertos y bases antes de
levantar servicios simultáneos.

Quedan derivados: smoke autenticado y revisión humana de los 10 hallazgos;
evaluaciones RAG/Mercado; pruebas transaccionales MeLi; Ruff/Alembic y
documentación operativa; finalmente los gates LAN, carga, failover y rollback.
Growen continúa en piloto/preproducción y no en producción verificada.
