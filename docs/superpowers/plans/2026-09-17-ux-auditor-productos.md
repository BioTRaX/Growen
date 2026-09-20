<!-- NG-HEADER: Nombre de archivo: 2026-09-17-ux-auditor-productos.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/plans/2026-09-17-ux-auditor-productos.md -->
<!-- NG-HEADER: Descripción: Plan de implementación para identificar y resolver revisiones del auditor desde Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# UX del auditor y resolución desde Productos — Plan de implementación

> **Para agentes ejecutores:** SUB-SKILL OBLIGATORIA: usar `superpowers:executing-plans` para ejecutar este plan por tareas y checkpoints. No usar subagentes salvo solicitud explícita del usuario. Cada paso utiliza casillas (`- [ ]`) para seguimiento.

**Objetivo:** mostrar el nombre real y la ficha vinculada de cada canónico auditado, y permitir que un administrador acepte desde Productos una revisión `needs_review` con nota y trazabilidad.

**Arquitectura:** ampliar los payloads existentes sin migraciones: `GET /canonical-products/catalog-audits/{run_id}` resolverá nombre y producto interno en consultas agrupadas, y `GET /products` expondrá las coordenadas del último ítem auditado mediante un prefetch. Vue reutilizará el endpoint de resolución `accept_exception`; una nueva ventana de confirmación encapsulará la nota, el estado de carga y los errores, mientras la tabla sólo emitirá la intención del usuario.

**Stack técnico:** FastAPI, SQLAlchemy async, pytest, Vue 3, TypeScript, Vuetify, Vitest.

**Especificación:** `docs/features/CATALOG_AUDITOR.md` y el diseño aprobado en la conversación del 17 de septiembre de 2026.

## Restricciones globales

- No crear ni modificar tablas, modelos ni revisiones Alembic.
- No introducir dependencias nuevas.
- `accept_exception` significa confirmar que el producto revisado es correcto; no aplica correcciones sugeridas por IA.
- Sólo `admin` puede aceptar una revisión; `colaborador` conserva únicamente las acciones ya autorizadas por backend.
- La nota es obligatoria, se normaliza con `trim()` y debe conservar el mínimo backend de 3 caracteres.
- No agregar consultas por fila: nombres, vínculos y coordenadas de auditoría se resuelven por lote.
- Todo comando Python debe ejecutarse con `.\.venv\Scripts\python.exe`.
- No hacer stage, commit, push, merge ni despliegue sin una nueva autorización explícita.
- Preservar los cambios preexistentes de la rama `feat/auditor-catalogo-completo`.
- Documentar los cambios y actualizar cualquier información desactualizada en `Roadmap.md`, `README.md`, `CHANGELOG.md` y `docs/`.

## Estado al cierre del 2026-09-20

- Tareas 1 a 4 implementadas con ciclo RED–GREEN y contratos backend/Vue
  verificados.
- El smoke Vue autenticado recorrió los 29 nombres y enlaces, validó navegación
  por `Product.id`, permisos admin/colaborador y cancelación segura del diálogo.
- La revisión humana posterior aceptó los 10 hallazgos; PostgreSQL confirmó 29
  canónicos `clean`, 10 excepciones activas y 10 acciones `accept_exception`.
- Suite backend focal, suite Vue, typecheck, build, auditor documental, Ruff y
  `git diff --check` aprobaron. Los 15 hallazgos históricos de Ruff en el router
  tocado se sanearon con cambios semánticamente equivalentes.
- Una nueva corrida por clic queda diferida por decisión del usuario hasta que
  ingresen productos nuevos. El smoke local no se presenta como verificación
  del estado productivo actual.

---

## Mapa de archivos

**Backend**

- Modificar `services/routers/catalog_audits.py`: enriquecer cada ítem con `canonical_name` y `product_detail_id` mediante consultas agrupadas.
- Modificar `services/routers/catalog.py`: incluir `CatalogAuditItem` y precargar `catalog_audit_run_id`/`catalog_audit_item_id` para el listado de productos.
- Modificar `tests/test_catalog_audit_api.py`: validar identidad legible, vínculo interno y permisos de aceptación.
- Modificar `tests/test_products_search_canonical.py`: validar las coordenadas del último ítem de auditoría en `GET /products`.

**Frontend Vue**

- Modificar `frontend-vue/src/modules/catalog-audit/types.ts`: tipar `canonical_name` y `product_detail_id`.
- Modificar `frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.vue`: mostrar nombre, ID canónico y enlace a la ficha interna.
- Modificar `frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.spec.ts`: cubrir nombre enlazado y ausencia de ficha interna.
- Modificar `frontend-vue/src/modules/products/types.ts`: tipar las coordenadas de auditoría.
- Modificar `frontend-vue/src/modules/products/components/ProductsTable.vue`: emitir la intención `acceptAudit` sólo cuando corresponda.
- Crear `frontend-vue/src/modules/products/components/ProductsTable.spec.ts`: verificar visibilidad, permisos y emisión.
- Crear `frontend-vue/src/modules/products/components/CatalogAuditReviewDialog.vue`: confirmar `accept_exception` con nota, carga y error.
- Crear `frontend-vue/src/modules/products/components/CatalogAuditReviewDialog.spec.ts`: verificar contrato HTTP, validación y eventos.
- Modificar `frontend-vue/src/modules/products/views/ProductsImpactView.vue`: abrir el diálogo, refrescar el listado y notificar el resultado.

**Documentación**

- Modificar `docs/features/CATALOG_AUDITOR.md`, `docs/features/PRODUCTS_UI.md`, `Roadmap.md`, `README.md` y `CHANGELOG.md`.

---

### Tarea 1: Identidad y navegación en el payload del auditor

**Archivos:**

- Modificar: `tests/test_catalog_audit_api.py`
- Modificar: `services/routers/catalog_audits.py`

**Interfaces:**

- Consume: `CatalogAuditItem.canonical_product_id`, `ProductEquivalence.canonical_product_id` y `SupplierProduct.internal_product_id`.
- Produce: `_item_dict(..., canonical_name: str | None, product_detail_id: int | None)` y los campos JSON homónimos.

- [ ] **Paso 1: escribir el test fallido del canónico vinculado**

  Crear un canónico, un producto interno, proveedor, `SupplierProduct`, `ProductEquivalence`, corrida e ítem. Consultar la corrida y exigir:

  ```python
  assert body["items"][0]["canonical_name"] == "Maceta Soplada 20L"
  assert body["items"][0]["product_detail_id"] == product.id
  ```

- [ ] **Paso 2: cubrir el canónico sin ficha interna**

  Crear un segundo canónico sin equivalencias y exigir nombre presente pero vínculo nulo:

  ```python
  assert orphan["canonical_name"] == "Canónico sin ficha"
  assert orphan["product_detail_id"] is None
  ```

- [ ] **Paso 3: ejecutar RED**

  Ejecutar:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_catalog_audit_api.py -k "nombre_y_ficha" -q
  ```

  Resultado esperado: falla porque ambos campos aún no existen.

- [ ] **Paso 4: ampliar `_item_dict` sin cambiar los consumidores actuales**

  Añadir argumentos opcionales y serializarlos:

  ```python
  def _item_dict(
      item: CatalogAuditItem,
      *,
      content_revision: int | None = None,
      content_versions: list[dict] | None = None,
      canonical_name: str | None = None,
      product_detail_id: int | None = None,
  ) -> dict:
      return {
          # campos existentes
          "canonical_name": canonical_name,
          "product_detail_id": product_detail_id,
      }
  ```

- [ ] **Paso 5: resolver nombres y fichas en lote**

  Importar `ProductEquivalence` y `SupplierProduct`. En `get_catalog_audit`, obtener en una consulta los nombres de todos los `canonical_ids` y en otra consulta agrupada el menor `internal_product_id` no nulo por canónico. Para ítems internos huérfanos, usar `item.product_id` como `product_detail_id`.

  ```python
  canonical_rows = (await session.execute(
      select(CanonicalProduct.id, CanonicalProduct.name)
      .where(CanonicalProduct.id.in_(canonical_ids))
  )).all()
  names = dict(canonical_rows)

  linked_rows = (await session.execute(
      select(
          ProductEquivalence.canonical_product_id,
          func.min(SupplierProduct.internal_product_id),
      )
      .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
      .where(
          ProductEquivalence.canonical_product_id.in_(canonical_ids),
          SupplierProduct.internal_product_id.is_not(None),
      )
      .group_by(ProductEquivalence.canonical_product_id)
  )).all()
  product_links = dict(linked_rows)
  ```

- [ ] **Paso 6: ejecutar GREEN y regresión focal**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_catalog_audit_api.py -q
  ```

  Resultado esperado: todos los tests del contrato del auditor pasan.

- [ ] **Paso 7: checkpoint de revisión**

  Revisar `git diff -- services/routers/catalog_audits.py tests/test_catalog_audit_api.py`. No hacer stage ni commit.

---

### Tarea 2: Coordenadas del último ítem auditado en Productos

**Archivos:**

- Modificar: `tests/test_products_search_canonical.py`
- Modificar: `services/routers/catalog.py`

**Interfaces:**

- Consume: `CanonicalProduct.last_catalog_audit_item_id` y `CatalogAuditItem.run_id`.
- Produce por fila: `catalog_audit_item_id: int | None` y `catalog_audit_run_id: str | None`.

- [ ] **Paso 1: extender el seed y escribir el test fallido**

  Crear una corrida finalizada e ítem `needs_review`, asignar su ID a `CanonicalProduct.last_catalog_audit_item_id` y consultar `GET /products`. Exigir:

  ```python
  assert found["catalog_audit_status"] == "needs_review"
  assert found["catalog_audit_item_id"] == audit_item.id
  assert found["catalog_audit_run_id"] == audit_run.id
  ```

- [ ] **Paso 2: ejecutar RED**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_products_search_canonical.py -q
  ```

  Resultado esperado: falla porque `GET /products` todavía no entrega las coordenadas.

- [ ] **Paso 3: implementar un prefetch por página**

  Importar `CatalogAuditItem`, reunir los IDs no nulos después de materializar `rows` y construir un mapa sin N+1:

  ```python
  audit_item_ids = {
      cp_obj.last_catalog_audit_item_id
      for _, _, _, _, cp_obj in rows
      if cp_obj and cp_obj.last_catalog_audit_item_id
  }
  audit_items_by_id = {}
  if audit_item_ids:
      audit_rows = (await session.execute(
          select(CatalogAuditItem.id, CatalogAuditItem.run_id)
          .where(CatalogAuditItem.id.in_(audit_item_ids))
      )).all()
      audit_items_by_id = {item_id: run_id for item_id, run_id in audit_rows}
  ```

  Al serializar cada producto, incluir ambos campos sólo a partir del puntero persistido del canónico.

- [ ] **Paso 4: ejecutar GREEN y comprobar que los productos sin auditoría conservan nulos**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_products_search_canonical.py -q
  ```

- [ ] **Paso 5: ejecutar la regresión conjunta del backend**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_catalog_audit_api.py tests/test_products_search_canonical.py -q
  ```

- [ ] **Paso 6: checkpoint de revisión**

  Revisar el SQL generado y confirmar que el número de consultas es constante por página. No hacer stage ni commit.

---

### Tarea 3: Mostrar el nombre y abrir la ficha desde el auditor Vue

**Archivos:**

- Modificar: `frontend-vue/src/modules/catalog-audit/types.ts`
- Modificar: `frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.spec.ts`
- Modificar: `frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.vue`

**Interfaces:**

- Consume: `CatalogAuditItem.canonical_name` y `CatalogAuditItem.product_detail_id`.
- Produce: un nombre legible; un `router-link` a `/productos/{product_detail_id}` si existe vínculo; texto “Sin ficha interna vinculada” si no existe.

- [ ] **Paso 1: tipar el contrato esperado en los datos de prueba**

  Agregar al ítem de prueba:

  ```ts
  canonical_name: 'Maceta Soplada 20L',
  product_detail_id: 17,
  ```

- [ ] **Paso 2: escribir los tests fallidos de presentación**

  Verificar que el nombre aparece, que el componente `RouterLink` recibe `/productos/17` y que un ítem sin `product_detail_id` muestra “Sin ficha interna vinculada” sin construir una URL con el ID canónico.

- [ ] **Paso 3: ejecutar RED**

  ```powershell
  npm.cmd test -- src/modules/catalog-audit/views/CatalogAuditView.spec.ts
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 4: ampliar el tipo TypeScript**

  ```ts
  canonical_name: string | null
  product_detail_id: number | null
  ```

- [ ] **Paso 5: reemplazar “Canónico #” como etiqueta principal**

  Renderizar `item.canonical_name ?? 'Producto sin nombre'`, conservar `Canónico #ID` como dato secundario y utilizar siempre `product_detail_id` para navegar. La acción “Editar ficha” debe usar el mismo campo, no `canonical_product_id` ni el `product_id` histórico.

- [ ] **Paso 6: ejecutar GREEN**

  ```powershell
  npm.cmd test -- src/modules/catalog-audit/views/CatalogAuditView.spec.ts
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 7: checkpoint de revisión visual del template**

  Confirmar que nombre, ID auxiliar, estado sin vínculo y acciones caben en tabla compacta y conservan navegación por teclado. No hacer stage ni commit.

---

### Tarea 4: Acción administrada “Aceptar revisión” en Productos

**Archivos:**

- Modificar: `frontend-vue/src/modules/products/types.ts`
- Crear: `frontend-vue/src/modules/products/components/ProductsTable.spec.ts`
- Modificar: `frontend-vue/src/modules/products/components/ProductsTable.vue`
- Crear: `frontend-vue/src/modules/products/components/CatalogAuditReviewDialog.spec.ts`
- Crear: `frontend-vue/src/modules/products/components/CatalogAuditReviewDialog.vue`
- Modificar: `frontend-vue/src/modules/products/views/ProductsImpactView.vue`

**Interfaces:**

- Consume: `catalog_audit_run_id`, `catalog_audit_item_id`, `catalog_audit_status` y `resolveCatalogAuditItem(runId, itemId, payload)`.
- Produce: evento `acceptAudit(product)`, diálogo controlado por `v-model`, evento `resolved(product)` y refresco del listado.

- [ ] **Paso 1: ampliar `ProductListItem`**

  ```ts
  catalog_audit_status?: string | null
  catalog_audit_run_id?: string | null
  catalog_audit_item_id?: number | null
  ```

- [ ] **Paso 2: escribir el test fallido de la tabla**

  Montar `ProductsTable` con un producto `needs_review`, coordenadas completas y `canResolveAudit: true`; exigir el botón “Aceptar revisión” y que al hacer click emita el producto. Repetir con `canResolveAudit: false` y exigir ausencia del botón.

- [ ] **Paso 3: ejecutar RED de la tabla**

  ```powershell
  npm.cmd test -- src/modules/products/components/ProductsTable.spec.ts
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 4: implementar la acción presentacional**

  Añadir la prop `canResolveAudit: boolean` y el evento:

  ```ts
  acceptAudit: [product: ProductListItem]
  ```

  Mostrar el botón únicamente cuando el rol recibido lo habilita, el estado es `needs_review` y existen `catalog_audit_run_id`/`catalog_audit_item_id`.

- [ ] **Paso 5: escribir los tests fallidos del diálogo**

  Mockear `resolveCatalogAuditItem`. Comprobar:

  - confirmación deshabilitada con menos de 3 caracteres útiles;
  - llamada con `{ action: 'accept_exception', note: 'Producto verificado' }`;
  - emisión `resolved` y cierre al resolver;
  - mensaje legible si la petición falla, conservando el diálogo abierto.

- [ ] **Paso 6: ejecutar RED del diálogo**

  ```powershell
  npm.cmd test -- src/modules/products/components/CatalogAuditReviewDialog.spec.ts
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 7: implementar el diálogo autocontenido**

  El componente recibe:

  ```ts
  defineProps<{
    modelValue: boolean
    product: ProductListItem | null
  }>()
  ```

  Normaliza la nota con `trim()`, llama al API existente, gestiona `loading`/`error` y emite:

  ```ts
  'update:modelValue': [value: boolean]
  resolved: [product: ProductListItem]
  ```

  Debe rechazar localmente la operación si faltan las coordenadas, aunque el botón de la tabla ya las filtre.

- [ ] **Paso 8: ejecutar GREEN de tabla y diálogo**

  ```powershell
  npm.cmd test -- src/modules/products/components/ProductsTable.spec.ts src/modules/products/components/CatalogAuditReviewDialog.spec.ts
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 9: integrar en `ProductsImpactView`**

  Crear `auditReviewProduct = ref<ProductListItem | null>(null)`, pasar `:can-resolve-audit="auth.role === 'admin'"`, escuchar `@accept-audit`, montar el diálogo y, en `@resolved`, cerrar, ejecutar `retry()` y mostrar un snackbar de éxito.

- [ ] **Paso 10: verificar permisos por ambas capas**

  Confirmar que un colaborador no ve la acción en Vue y que el test backend existente `test_colaborador_no_puede_clasificar_item` se complementa con un caso explícito para `accept_exception` que espere HTTP 403.

- [ ] **Paso 11: checkpoint de revisión**

  Revisar que aceptar no aplique correcciones, no dispare una reauditoría y no modifique identidad, dinero ni fuentes únicas. No hacer stage ni commit.

---

### Tarea 5: Documentación, verificación y smoke manual

**Archivos:**

- Modificar: `docs/features/CATALOG_AUDITOR.md`
- Modificar: `docs/features/PRODUCTS_UI.md`
- Modificar: `Roadmap.md`
- Modificar: `README.md`
- Modificar: `CHANGELOG.md`

**Interfaces:**

- Consume: comportamiento verificado en las tareas 1–4.
- Produce: documentación coherente que distingue código integrado, piloto desplegado y producción verificada.

- [ ] **Paso 1: actualizar documentación viva**

  Documentar los nuevos campos de lectura, la navegación por ficha, el flujo `needs_review → accept_exception → clean`, el requisito de nota y la restricción admin. No declarar producción completa ni despliegue realizado.

- [ ] **Paso 2: ejecutar pruebas backend focales**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_catalog_audit_api.py tests/test_products_search_canonical.py -q
  ```

- [ ] **Paso 3: ejecutar pruebas Vue focales**

  ```powershell
  npm.cmd test -- src/modules/catalog-audit/views/CatalogAuditView.spec.ts src/modules/products/components/ProductsTable.spec.ts src/modules/products/components/CatalogAuditReviewDialog.spec.ts
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 4: ejecutar gates Vue completos**

  ```powershell
  npm.cmd test
  npm.cmd run typecheck
  npm.cmd run build
  ```

  Directorio: `frontend-vue`.

- [ ] **Paso 5: auditar documentación y lint focal**

  ```powershell
  .\.venv\Scripts\python.exe scripts\audit_docs.py
  .\.venv\Scripts\python.exe -m ruff check services/routers/catalog.py services/routers/catalog_audits.py tests/test_catalog_audit_api.py tests/test_products_search_canonical.py
  ```

- [ ] **Paso 6: ejecutar smoke manual autenticado en Vue**

  Con sesión admin en el entorno local:

  1. Abrir `/admin/auditor-catalogo` y verificar que los 29 canónicos muestran nombre.
  2. Abrir al menos una ficha desde el nombre y confirmar que `/productos/{product_detail_id}` corresponde al producto correcto.
  3. Verificar el estado explícito para un canónico sin ficha interna, si existe.
  4. Abrir `/productos`, aceptar un `needs_review` con una nota no sensible y comprobar que el badge pasa a `clean` después del refresco.
  5. Confirmar en el auditor que resolución, usuario y nota quedan trazables.
  6. Con rol colaborador, confirmar que la acción de aceptación no está visible y que una llamada directa devuelve 403.

- [ ] **Paso 7: ejecutar verificación final del árbol**

  ```powershell
  git status --short --branch
  git diff --check
  git diff --stat
  ```

  Separar en el informe los cambios previos de Fase 2 de los añadidos por esta mejora.

- [ ] **Paso 8: solicitar revisión de código**

  Aplicar `superpowers:requesting-code-review` únicamente cuando todos los comandos anteriores tengan evidencia reciente. Corregir hallazgos bloqueantes y repetir los gates afectados.

- [ ] **Paso 9: cerrar la ejecución sin integrar**

  Liberar los locks cooperativos adquiridos para la tarea. Informar archivos, pruebas y deuda residual. No hacer stage, commit, push, merge ni despliegue.

---

## Criterios de aceptación

- El auditor muestra el nombre canónico como identidad principal y conserva el ID sólo como referencia secundaria.
- El enlace de la fila utiliza un `Product.id` interno válido; nunca intenta abrir una ficha usando `CanonicalProduct.id`.
- Los canónicos sin ficha muestran un estado explícito y no generan enlaces rotos.
- `GET /products` entrega las coordenadas del último ítem auditado sin consultas por fila.
- Sólo un administrador ve y puede ejecutar “Aceptar revisión”.
- La aceptación exige una nota de al menos 3 caracteres, reutiliza `accept_exception`, deja el estado en `clean` y conserva feedback, usuario y fecha en backend.
- Ninguna recomendación ni corrección de IA se aplica como parte de este flujo.
- Pasan las pruebas backend y Vue focales, la suite Vue, typecheck, build, auditor documental, Ruff focal y `git diff --check`.
- El smoke autenticado se ejecuta sobre ambos recorridos de UI y no se presenta como validado si no pudo completarse.
- Se documentan los cambios y se actualiza cualquier información desactualizada en `Roadmap.md`, `README.md`, `CHANGELOG.md` y `docs/`.
- El estado final distingue explícitamente entre código integrado, piloto desplegado y producción verificada.
