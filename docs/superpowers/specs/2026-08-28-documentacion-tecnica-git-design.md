<!-- NG-HEADER: Nombre de archivo: 2026-08-28-documentacion-tecnica-git-design.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/specs/2026-08-28-documentacion-tecnica-git-design.md -->
<!-- NG-HEADER: Descripción: Diseño para ordenar gradualmente la documentación técnica versionada en Git. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Organización de documentación técnica en Git

## Objetivo

Crear una entrada única y navegable para la documentación técnica de Growen,
clasificar los documentos existentes por propósito y establecer reglas para
mantener una fuente canónica por tema, sin mover ni eliminar archivos durante
la primera fase.

## Alcance de esta fase

Incluye:

- Crear `docs/README.md` como índice documental principal.
- Definir estados documentales: `canónico`, `operativo`, `evidencia`,
  `histórico` y `temporal`.
- Agrupar el inventario por dominios funcionales y transversales mediante
  enlaces, conservando las rutas actuales.
- Explicar la responsabilidad de `README.md`, `Roadmap.md`, `CHANGELOG.md`,
  `docs/README.md` y `docs/archive/`.
- Registrar criterios para declarar un documento vigente, reemplazado o
  archivado.
- Identificar explícitamente los documentos que requieren una segunda fase de
  consolidación.

No incluye:

- Mover, renombrar o eliminar documentos existentes.
- Reescribir el contenido técnico de los documentos de dominio.
- Publicar documentos en SiYuan.
- Resolver todos los enlaces históricos en esta misma fase.

## Taxonomía

Cada documento enlazado desde el índice tendrá una función principal:

| Estado | Uso | Ejemplos |
|---|---|---|
| Canónico | Contrato técnico vigente o descripción de arquitectura actual | API, seguridad, modelos, frontend vigente |
| Operativo | Procedimiento reproducible de desarrollo, despliegue o diagnóstico | workflow, testing, workers, troubleshooting |
| Evidencia | Resultado fechado de un smoke, incidente, migración o validación | deployment smoke, security incident |
| Histórico | Diseño, estado o guía reemplazada que se conserva por trazabilidad | `docs/archive/`, historial del roadmap |
| Temporal | Handoff o nota de transición con vigencia limitada | handoffs y planes de una entrega |

El estado se expresará en el índice y no se añadirá metadata obligatoria a los
documentos existentes en esta primera fase.

## Estructura del índice

`docs/README.md` tendrá estas secciones:

1. Cómo usar la documentación y cuál es la fuente de verdad.
2. Documentos raíz y responsabilidades.
3. Arquitectura y plataforma.
4. APIs, seguridad y base de datos.
5. Dominios de producto: catálogo, compras, ventas, stock, mercado, imágenes,
   conocimiento, chat e importaciones.
6. Frontend y migración Vue.
7. Operación, workers, despliegue y diagnóstico.
8. Agentes, MCP y SiYuan.
9. Evidencias, retrospectivas, handoffs y archivo histórico.
10. Reglas para crear y actualizar documentación.

Cada entrada deberá indicar el estado, enlazar al archivo real y evitar
duplicar su contenido.

## Responsabilidades de los documentos principales

- `README.md`: orientación inicial, estado resumido y enlaces de entrada.
- `Roadmap.md`: pendientes y trabajo futuro; no repetir historial cerrado.
- `CHANGELOG.md`: cambios entregados por versión o hito.
- `docs/README.md`: mapa técnico completo y clasificación documental.
- `docs/archive/README.md`: catálogo de documentos reemplazados y destino de
  consulta vigente.
- Retrospectivas y handoffs: evidencia fechada o transición; no sustituyen el
  contrato técnico canónico.

## Migración posterior

Después de validar el índice, la documentación se consolidará por dominios en
orden de mayor valor y menor riesgo: plataforma y gobernanza, API/seguridad,
frontend, dominios de negocio y finalmente evidencias históricas. Cada lote
deberá actualizar enlaces, comprobar referencias y registrar los movimientos
en `docs/archive/README.md`.

## Validación

La primera fase se considerará válida cuando:

- Todos los documentos técnicos activos importantes estén accesibles desde
  `docs/README.md`.
- El lector pueda distinguir contrato vigente, operación, evidencia e
  histórico sin inspeccionar cada archivo.
- No se hayan alterado archivos de código ni documentos ajenos al alcance.
- `README.md`, `Roadmap.md` y `docs/` describan el mismo flujo documental.
- Se documenten los cambios y se actualice cualquier contenido desactualizado.
