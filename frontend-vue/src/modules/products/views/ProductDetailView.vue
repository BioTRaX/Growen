<!-- NG-HEADER: Nombre de archivo: ProductDetailView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/views/ProductDetailView.vue -->
<!-- NG-HEADER: Descripción: Detalle operativo canónico de producto en Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../../../auth/store'
import { getProductSources } from '../../market/api/market'
import type { ProductSources } from '../../market/types'
import { getHttpErrorMessage } from '../../../services/http'
import { getProduct, getProductHistory } from '../api/products'
import CanonicalSkuEditor from '../components/CanonicalSkuEditor.vue'
import EnrichmentPanel from '../components/EnrichmentPanel.vue'
import StructuredProductData from '../components/StructuredProductData.vue'
import TagManagementDialog from '../components/TagManagementDialog.vue'
import { useEnrichmentJob } from '../composables/useEnrichmentJob'
import type { EnrichmentScope, ProductDetail, ProductPurchaseHistory } from '../types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const product = ref<ProductDetail | null>(null)
const history = ref<ProductPurchaseHistory | null>(null)
const market = ref<ProductSources | null>(null)
const loading = ref(false)
const error = ref('')
const tagsOpen = ref(false)
const productId = Number(route.params.id)
const canViewOperational = computed(() => auth.role === 'admin' || auth.role === 'colaborador')
const canEditCanonicalSku = computed(() => auth.role === 'admin' || auth.role === 'colaborador')
const enrich = useEnrichmentJob(async () => load())

const historyHeaders = [
  { title: 'Fecha', key: 'date' },
  { title: 'Proveedor', key: 'supplier.name' },
  { title: 'Remito', key: 'remito_number' },
  { title: 'Cantidad', key: 'quantity', align: 'end' as const },
  { title: 'Costo neto', key: 'net_unit_cost', align: 'end' as const },
  { title: '', key: 'attachment_url', sortable: false },
]

function money(value: number | null): string {
  return value === null ? '—' : new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

function valueText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

async function load(): Promise<void> {
  if (!Number.isInteger(productId) || productId < 1) {
    error.value = 'Identificador de producto inválido'
    return
  }
  loading.value = true
  error.value = ''
  try {
    product.value = await getProduct(productId)
    const requests: Promise<unknown>[] = []
    if (product.value.canonical_product_id && product.value.enrichment?.job_id) {
      requests.push(enrich.resume(product.value.canonical_product_id, product.value.enrichment.job_id))
    }
    if (canViewOperational.value) {
      requests.push(getProductHistory(productId).then((value) => { history.value = value }))
      if (product.value.canonical_product_id) {
        requests.push(
          getProductSources(product.value.canonical_product_id)
            .then((value) => { market.value = value })
            .catch(() => { market.value = null }),
        )
      }
    }
    await Promise.all(requests)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo cargar el detalle del producto')
  } finally {
    loading.value = false
  }
}

async function startEnrichment(scope: EnrichmentScope): Promise<void> {
  if (!product.value?.canonical_product_id) return
  await enrich.start(product.value.canonical_product_id, productId, scope)
}

async function applyFields(fields: string[]): Promise<void> {
  if (!product.value?.canonical_product_id || product.value.content_revision === null) return
  await enrich.apply(product.value.canonical_product_id, product.value.content_revision, fields)
}

async function discardProposal(): Promise<void> {
  if (product.value?.canonical_product_id) await enrich.discard(product.value.canonical_product_id)
}

async function tagsSaved(): Promise<void> {
  tagsOpen.value = false
  await load()
}

function skuSaved(sku: string): void {
  if (product.value) product.value.canonical_sku = sku
}

onMounted(load)
</script>

<template>
  <v-container class="py-8" fluid>
    <v-btn prepend-icon="mdi-arrow-left" variant="text" @click="router.back()">Volver</v-btn>
    <v-progress-linear v-if="loading" class="my-6" color="primary" indeterminate />
    <v-alert v-if="error" class="my-6" type="error" variant="tonal">
      {{ error }}
      <template #append><v-btn size="small" variant="text" @click="load">Reintentar</v-btn></template>
    </v-alert>

    <template v-if="product">
      <header class="d-flex flex-wrap align-center justify-space-between ga-3 my-5">
        <div>
          <h1 class="text-h4">{{ product.preferred_title || product.title }}</h1>
          <CanonicalSkuEditor
            :canonical-product-id="product.canonical_product_id"
            :editable="canEditCanonicalSku"
            :fallback-sku="product.sku_root"
            :sku="product.canonical_sku"
            @saved="skuSaved"
          />
        </div>
        <div class="d-flex flex-wrap ga-2">
          <v-chip :color="product.canonical_product_id ? 'success' : 'warning'" variant="tonal">
            {{ product.canonical_product_id ? 'Contenido canónico' : 'Canónico requerido' }}
          </v-chip>
          <v-btn v-if="canViewOperational" href="/stock" prepend-icon="mdi-warehouse" variant="tonal">Gestionar stock</v-btn>
          <v-btn
            v-if="canViewOperational && product.canonical_product_id"
            :to="{ name: 'product-knowledge', params: { id: product.id } }"
            prepend-icon="mdi-bookshelf"
            variant="tonal"
          >
            Conocimiento
          </v-btn>
          <v-btn v-if="canViewOperational" :href="`/productos/${product.id}/imagen`" prepend-icon="mdi-image-edit" variant="tonal">
            Imágenes avanzadas
          </v-btn>
        </div>
      </header>

      <v-alert v-if="product.canonical_status === 'canonical_required'" type="warning" variant="tonal" class="mb-5">
        Esta ficha muestra los datos internos básicos. Para generar contenido hay que crear o asignar un producto canónico desde la administración de equivalencias.
        <template #append>
          <v-btn v-if="canViewOperational" to="/productos" variant="text">Crear o asignar canónico</v-btn>
        </template>
      </v-alert>

      <v-row>
        <v-col cols="12" md="4"><v-card><v-card-title>Stock agregado</v-card-title><v-card-text class="text-h5">{{ product.stock_total }}</v-card-text></v-card></v-col>
        <v-col cols="12" md="4"><v-card><v-card-title>Precio efectivo</v-card-title><v-card-text class="text-h5">{{ money(product.sale_price) }}</v-card-text></v-card></v-col>
        <v-col cols="12" md="4"><v-card><v-card-title>Categoría</v-card-title><v-card-text class="text-h6">{{ product.category_path || 'Sin categoría' }}</v-card-text></v-card></v-col>
      </v-row>

      <v-row class="mt-2">
        <v-col cols="12" lg="8">
          <v-card>
            <v-card-title>Descripción</v-card-title>
            <v-card-text v-if="product.description_html" class="product-description" v-html="product.description_html" />
            <v-card-text v-else class="text-medium-emphasis">Todavía no hay una descripción canónica.</v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" lg="4">
          <v-card>
            <v-card-title>Datos técnicos</v-card-title>
            <v-list density="compact">
              <v-list-item title="Peso" :subtitle="product.weight_kg === null ? '—' : `${product.weight_kg} kg`" />
              <v-list-item title="Dimensiones" :subtitle="`${valueText(product.width_cm)} × ${valueText(product.depth_cm)} × ${valueText(product.height_cm)} cm`" />
            </v-list>
            <v-divider />
            <v-card-text>
              <div class="text-subtitle-2">Especificaciones</div>
              <StructuredProductData class="text-body-2" :value="product.technical_specs" />
              <div class="text-subtitle-2 mt-3">Instrucciones</div>
              <StructuredProductData class="text-body-2" :value="product.usage_instructions" />
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col v-if="canViewOperational && product.canonical_product_id" cols="12" lg="8">
          <EnrichmentPanel
            :error="enrich.error.value"
            :job="enrich.job.value"
            :loading="enrich.loading.value"
            @apply="applyFields"
            @discard="discardProposal"
            @start="startEnrichment"
          />
        </v-col>
        <v-col v-if="canViewOperational && product.canonical_product_id" cols="12" lg="4">
          <v-card>
            <v-card-title>Mercado</v-card-title>
            <v-card-text>
              <div class="text-caption">Referencia validada</div>
              <div class="text-h5">{{ money(market?.market_price_reference ?? null) }}</div>
              <p class="text-medium-emphasis">
                {{ market ? `${market.mandatory.length + market.additional.length} fuentes configuradas` : 'Sin información disponible' }}
              </p>
              <v-btn to="/mercado" prepend-icon="mdi-chart-line" variant="tonal">Abrir Mercado</v-btn>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-card class="mt-6">
        <v-card-title>Imágenes vinculadas</v-card-title>
        <v-card-text class="d-flex flex-wrap ga-3">
          <v-img v-for="image in product.images" :key="image.id" :alt="image.alt_text || product.preferred_title || product.title" :src="image.url" cover height="150" width="150" />
          <span v-if="!product.images.length" class="text-medium-emphasis">Sin imágenes activas.</span>
        </v-card-text>
      </v-card>

      <v-card class="mt-6">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>Tags vinculados</span>
          <v-btn v-if="auth.isStaff" prepend-icon="mdi-pencil" size="small" variant="text" @click="tagsOpen = true">Editar este registro</v-btn>
        </v-card-title>
        <v-card-text class="d-flex flex-wrap ga-2">
          <v-chip v-for="tag in product.tags" :key="tag.id" prepend-icon="mdi-tag-outline">{{ tag.name }}</v-chip>
          <span v-if="!product.tags.length" class="text-medium-emphasis">Sin tags</span>
        </v-card-text>
      </v-card>

      <v-card v-if="canViewOperational && history" class="mt-6">
        <v-card-title>Historial operativo del registro solicitado</v-card-title>
        <v-data-table :headers="historyHeaders" :items="history.items">
          <template #item.net_unit_cost="{ value }">{{ money(value) }}</template>
          <template #item.attachment_url="{ value }"><v-btn v-if="value" :href="value" size="small" target="_blank" variant="text">Documento</v-btn></template>
          <template #no-data><div class="pa-6 text-center text-medium-emphasis">No hay compras confirmadas.</div></template>
        </v-data-table>
      </v-card>

      <v-card class="mt-6">
        <v-card-title>Inventario vinculado</v-card-title>
        <v-card-subtitle>Cada Product.id aparece una sola vez; el stock es sólo lectura.</v-card-subtitle>
        <v-list lines="three">
          <v-list-item v-for="item in product.linked_inventory" :key="item.product_id">
            <v-list-item-title>#{{ item.product_id }} · {{ item.original_name }}</v-list-item-title>
            <v-list-item-subtitle>
              Stock {{ item.stock }} · {{ item.sku_root || 'sin SKU' }}<br>
              {{ item.suppliers.map((supplier) => supplier.supplier_name).join(', ') || 'Sin proveedores relacionados' }}
            </v-list-item-subtitle>
            <template #append>
              <v-btn :to="item.product_url" icon="mdi-open-in-new" title="Abrir registro" variant="text" />
              <v-btn :href="item.stock_url" icon="mdi-warehouse" title="Gestionar stock" variant="text" />
            </template>
          </v-list-item>
        </v-list>
      </v-card>
    </template>

    <TagManagementDialog
      v-if="product"
      v-model="tagsOpen"
      :current-tags="product.tags"
      :product-ids="[product.id]"
      @saved="tagsSaved"
    />
  </v-container>
</template>

<style scoped>
.product-description :deep(p) { margin-bottom: 0.75rem; }
</style>
