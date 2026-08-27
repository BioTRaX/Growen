<!-- NG-HEADER: Nombre de archivo: ProductsImpactView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/views/ProductsImpactView.vue -->
<!-- NG-HEADER: Descripción: Listado operativo del catálogo de Productos migrado a Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { enrichProducts, fillMissingSalePrices, listProductCategories, listProductSuppliers } from '../api/products'
import { generateCatalog } from '../../../services/catalogs'
import { apiUrl, downloadBlob } from '../../../services/transports'
import ProductCreateDialog from '../components/ProductCreateDialog.vue'
import ProductDeleteDialog from '../components/ProductDeleteDialog.vue'
import ProductPriceDialog from '../components/ProductPriceDialog.vue'
import ProductStockDialog from '../components/ProductStockDialog.vue'
import MassCanonicalDraftRecoveryDialog from '../components/MassCanonicalDraftRecoveryDialog.vue'
import MassCanonicalWizard from '../components/MassCanonicalWizard.vue'
import TagManagementDialog from '../components/TagManagementDialog.vue'
import CatalogHistoryDialog from '../components/CatalogHistoryDialog.vue'
import ProductsFilters from '../components/ProductsFilters.vue'
import ProductsTable from '../components/ProductsTable.vue'
import { useProductList } from '../composables/useProductList'
import { useMassCanonicalDraft } from '../composables/useMassCanonicalDraft'
import type { CanonicalBatchJobResponse, CreatedProduct, MassCanonicalDraftRow, ProductCategory, ProductDeleteResult, ProductListFilters, ProductListItem, ProductSupplier } from '../types'

const auth = useAuthStore()
const categories = ref<ProductCategory[]>([])
const suppliers = ref<ProductSupplier[]>([])
const metadataLoading = ref(false)
const metadataError = ref('')
const selected = ref<number[]>([])
const createOpen = ref(false)
const stockProduct = ref<ProductListItem | null>(null)
const priceProduct = ref<ProductListItem | null>(null)
const deleteProducts = ref<ProductListItem[]>([])
const snackbar = ref({ open: false, message: '', color: 'success' })
const wizardOpen = ref(false)
const recoveryOpen = ref(false)
const omittedCanonicalCount = ref(0)
const bulkTagsOpen = ref(false)
const catalogHistoryOpen = ref(false)
const operationLoading = ref('')
const { items, total, loading, error, filters, totalPages, setFilters, retry } = useProductList()
const massDraft = useMassCanonicalDraft(auth.user?.id ?? 0)
const selectedProducts = computed(() => {
  const ids = new Set(selected.value)
  return items.value.filter((item) => ids.has(item.product_id))
})

async function loadMetadata(): Promise<void> {
  metadataLoading.value = true
  metadataError.value = ''
  try {
    const [categoryRows, supplierRows] = await Promise.all([listProductCategories(), listProductSuppliers()])
    categories.value = categoryRows
    suppliers.value = supplierRows
  } catch (cause) {
    metadataError.value = getHttpErrorMessage(cause, 'No se pudieron cargar proveedores y categorías')
  } finally {
    metadataLoading.value = false
  }
}

function updateFilters(patch: Partial<ProductListFilters>): void {
  selected.value = []
  void setFilters(patch)
}

function notify(message: string, color: 'success' | 'info' | 'warning' | 'error' = 'success'): void {
  snackbar.value = { open: true, message, color }
}

async function runOperation(key: string, action: () => Promise<void>, success: string): Promise<void> {
  operationLoading.value = key
  try {
    await action()
    notify(success)
  } catch (cause) {
    notify(getHttpErrorMessage(cause), 'error')
  } finally { operationLoading.value = '' }
}

async function enrichSelection(): Promise<void> {
  const ids = [...selected.value]
  await runOperation('enrich', async () => { await enrichProducts(ids) }, `${ids.length} producto(s) enviados a enriquecimiento`)
  selected.value = []
  retry()
}

async function generateSelectionCatalog(): Promise<void> {
  const ids = [...selected.value]
  await runOperation('catalog', () => generateCatalog(ids), `Catálogo generado con ${ids.length} producto(s)`)
}

async function fillPrices(): Promise<void> {
  operationLoading.value = 'prices'
  try {
    const result = await fillMissingSalePrices(filters.value.supplier_id)
    notify(`Precios de venta completados: ${result.updated}`)
    retry()
  } catch (cause) { notify(getHttpErrorMessage(cause), 'error') } finally { operationLoading.value = '' }
}

function categoryCreated(category: ProductCategory): void {
  if (!categories.value.some((item) => item.id === category.id)) {
    categories.value = [...categories.value, category].sort((left, right) => left.path.localeCompare(right.path, 'es'))
  }
  notify(`${category.kind === 'subcategory' ? 'Subcategoría' : 'Categoría'} “${category.name}” creada`)
}

async function productCreated(_product: CreatedProduct): Promise<void> {
  await setFilters({ page: 1 }, false)
  retry()
  notify('Producto creado y vinculado al proveedor')
}

function stockSaved(stock: number): void {
  if (!stockProduct.value) return
  items.value = items.value.map((item) => item.product_id === stockProduct.value?.product_id ? { ...item, stock } : item)
  notify('Stock actualizado')
}

function priceSaved(price: number): void {
  if (!priceProduct.value) return
  const target = priceProduct.value
  items.value = items.value.map((item) => item.product_id !== target.product_id ? item : target.canonical_product_id
    ? { ...item, canonical_sale_price: price }
    : { ...item, precio_venta: price })
  notify('Precio de venta actualizado')
}

function requestBulkDelete(): void {
  const ids = new Set(selected.value)
  deleteProducts.value = items.value.filter((item) => ids.has(item.product_id))
}

function deleted(result: ProductDeleteResult): void {
  const deletedIds = new Set(result.deleted)
  items.value = items.value.filter((item) => !deletedIds.has(item.product_id))
  selected.value = selected.value.filter((id) => !deletedIds.has(id))
  total.value = Math.max(0, total.value - result.deleted.length)
  const blocked = result.blocked_stock.length + result.blocked_refs.length
  notify(
    `Borrados ${result.deleted.length} de ${result.requested.length}${blocked ? `. Bloqueados: ${blocked}` : ''}`,
    blocked ? 'warning' : 'success',
  )
}

function openMassCanonical(): void {
  const seen = new Set<number>()
  const rows: MassCanonicalDraftRow[] = []
  let omitted = 0
  selectedProducts.value.forEach((product) => {
    if (product.canonical_product_id || !product.supplier_item_id || seen.has(product.supplier_item_id)) {
      omitted += 1
      return
    }
    seen.add(product.supplier_item_id)
    rows.push({
      sourceProductId: product.supplier_item_id,
      internalProductId: product.product_id,
      sourceName: product.preferred_name || product.name,
      supplierName: product.supplier.name,
      name: product.preferred_name || product.name,
      brand: '',
      categoryId: null,
      subcategoryId: null,
      tagNames: [],
      previewSku: null,
    })
  })
  omittedCanonicalCount.value = omitted
  if (!rows.length) {
    notify('La selección no contiene productos de proveedor pendientes de canonizar', 'warning')
    return
  }
  massDraft.create(rows)
  wizardOpen.value = true
}

function discardMassDraft(): void {
  massDraft.discard()
  wizardOpen.value = false
  recoveryOpen.value = false
}

function resumeMassDraft(): void {
  recoveryOpen.value = false
  wizardOpen.value = true
}

function canonicalBatchCompleted(job: CanonicalBatchJobResponse): void {
  retry()
  const successfulSourceIds = new Set(job.items.filter((item) => item.status === 'SUCCEEDED').map((item) => item.source_product_id))
  selected.value = selected.value.filter((productId) => {
    const product = items.value.find((row) => row.product_id === productId)
    return !product?.supplier_item_id || !successfulSourceIds.has(product.supplier_item_id)
  })
  notify(
    job.status === 'COMPLETED'
      ? `Se crearon ${job.success_count} productos canónicos`
      : `Lote finalizado: ${job.success_count} creados y ${job.error_count} con error`,
    job.status === 'COMPLETED' ? 'success' : 'warning',
  )
}

onMounted(() => {
  void loadMetadata()
  if (massDraft.load()) recoveryOpen.value = true
})
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-5">
      <div>
        <h1 class="text-h4">Catálogo de Productos</h1>
        <p class="text-medium-emphasis mb-0">Consulta de productos, stock, precios y estado de canonización.</p>
      </div>
      <div class="d-flex align-center ga-2">
        <v-chip color="primary" prepend-icon="mdi-package-variant" variant="tonal">
          {{ total }} resultado{{ total === 1 ? '' : 's' }}
        </v-chip>
        <v-btn v-if="auth.isStaff" :loading="operationLoading === 'prices'" prepend-icon="mdi-currency-usd" variant="tonal" @click="fillPrices">Completar precios</v-btn>
        <v-btn v-if="auth.isStaff" prepend-icon="mdi-history" variant="tonal" @click="catalogHistoryOpen = true">Catálogos</v-btn>
        <v-btn v-if="auth.isStaff" :href="apiUrl('/catalogs/latest')" prepend-icon="mdi-eye" target="_blank" variant="tonal">Ver catálogo actual</v-btn>
        <v-btn v-if="auth.isStaff" prepend-icon="mdi-download" variant="tonal" @click="downloadBlob('/catalogs/latest/download', 'ultimo_catalogo.pdf')">Descargar catálogo</v-btn>
        <v-btn v-if="auth.isStaff" color="primary" prepend-icon="mdi-plus" @click="createOpen = true">Nuevo producto</v-btn>
      </div>
    </div>

    <v-alert
      v-if="metadataError"
      class="mb-4"
      closable
      color="warning"
      type="warning"
      variant="tonal"
      @click:close="metadataError = ''"
    >
      {{ metadataError }}. La búsqueda por texto continúa disponible.
      <template #append><v-btn size="small" variant="text" @click="loadMetadata">Reintentar</v-btn></template>
    </v-alert>

    <ProductsFilters
      :categories="categories"
      :metadata-loading="metadataLoading"
      :model-value="filters"
      :suppliers="suppliers"
      @update:model-value="updateFilters"
    />

    <v-alert v-if="error" class="mb-4" color="error" type="error" variant="tonal">
      {{ error }}
      <template #append><v-btn size="small" variant="text" @click="retry">Reintentar</v-btn></template>
    </v-alert>

    <v-card>
      <div v-if="auth.isStaff && selected.length" class="d-flex align-center ga-3 pa-3">
        <span class="text-body-2">{{ selected.length }} seleccionado(s)</span>
        <v-btn color="primary" prepend-icon="mdi-source-branch" size="small" variant="tonal" @click="openMassCanonical">Crear canónicos</v-btn>
        <v-btn :loading="operationLoading === 'catalog'" prepend-icon="mdi-file-pdf-box" size="small" variant="tonal" @click="generateSelectionCatalog">Generar catálogo</v-btn>
        <v-btn :loading="operationLoading === 'enrich'" prepend-icon="mdi-auto-fix" size="small" variant="tonal" @click="enrichSelection">Enriquecer</v-btn>
        <v-btn prepend-icon="mdi-tag-multiple-outline" size="small" variant="tonal" @click="bulkTagsOpen = true">Agregar tags</v-btn>
        <v-btn color="error" prepend-icon="mdi-delete-outline" size="small" variant="tonal" @click="requestBulkDelete">Borrar seleccionados</v-btn>
        <v-btn size="small" variant="text" @click="selected = []">Limpiar selección</v-btn>
      </div>
      <ProductsTable
        :can-edit="auth.isStaff"
        :items="items"
        :loading="loading"
        :selected="selected"
        @delete="deleteProducts = [$event]"
        @edit-price="priceProduct = $event"
        @edit-stock="stockProduct = $event"
        @update:selected="selected = $event"
      />
      <v-divider />
      <div class="d-flex flex-wrap align-center justify-space-between ga-3 pa-4">
        <v-select
          density="compact"
          hide-details
          :items="[25, 50, 100]"
          label="Filas"
          :model-value="filters.page_size"
          style="max-width: 120px"
          @update:model-value="setFilters({ page_size: Number($event), page: 1 }, false)"
        />
        <v-pagination
          :disabled="loading"
          :length="totalPages"
          :model-value="filters.page"
          :total-visible="7"
          @update:model-value="setFilters({ page: $event }, false)"
        />
      </div>
    </v-card>

    <ProductCreateDialog
      v-model="createOpen"
      :categories="categories"
      @category-created="categoryCreated"
      @created="productCreated"
    />
    <ProductStockDialog :model-value="Boolean(stockProduct)" :product="stockProduct" @saved="stockSaved" @update:model-value="!$event && (stockProduct = null)" />
    <ProductPriceDialog :model-value="Boolean(priceProduct)" :product="priceProduct" @saved="priceSaved" @update:model-value="!$event && (priceProduct = null)" />
    <ProductDeleteDialog :model-value="Boolean(deleteProducts.length)" :products="deleteProducts" @deleted="deleted" @update:model-value="!$event && (deleteProducts = [])" />
    <MassCanonicalDraftRecoveryDialog
      v-model="recoveryOpen"
      :draft="massDraft.draft.value"
      @discard="discardMassDraft"
      @resume="resumeMassDraft"
    />
    <MassCanonicalWizard
      v-model="wizardOpen"
      :categories="categories"
      :draft="massDraft.draft.value"
      :omitted-count="omittedCanonicalCount"
      @category-created="categoryCreated"
      @completed="canonicalBatchCompleted"
      @discard="discardMassDraft"
    />
    <TagManagementDialog
      v-model="bulkTagsOpen"
      bulk
      :product-ids="selected"
      @saved="retry(); notify('Tags asignados a la selección')"
    />
    <CatalogHistoryDialog v-model="catalogHistoryOpen" />
    <v-snackbar v-model="snackbar.open" :color="snackbar.color" timeout="4500">{{ snackbar.message }}</v-snackbar>
  </v-container>
</template>
