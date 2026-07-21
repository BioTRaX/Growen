<!-- NG-HEADER: Nombre de archivo: ProductPurchaseHistoryView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/views/ProductPurchaseHistoryView.vue -->
<!-- NG-HEADER: Descripción: Detalle básico e historial de compras de un producto en Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { getProduct, getProductHistory } from '../api/products'
import type { ProductDetail, ProductPurchaseHistory } from '../types'
import TagManagementDialog from '../components/TagManagementDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const product = ref<ProductDetail | null>(null)
const history = ref<ProductPurchaseHistory | null>(null)
const loading = ref(false)
const error = ref('')
const productId = Number(route.params.id)
const canViewHistory = computed(() => auth.role === 'admin' || auth.role === 'colaborador')
const tagsOpen = ref(false)

const historyHeaders = [
  { title: 'Fecha', key: 'date' },
  { title: 'Proveedor', key: 'supplier.name' },
  { title: 'Remito', key: 'remito_number' },
  { title: 'Cantidad', key: 'quantity', align: 'end' as const },
  { title: 'Costo bruto', key: 'gross_unit_cost', align: 'end' as const },
  { title: 'Bonif. %', key: 'discount_pct', align: 'end' as const },
  { title: 'Costo neto', key: 'net_unit_cost', align: 'end' as const },
  { title: '', key: 'attachment_url', sortable: false },
]

function formatPrice(value: number | null): string {
  return value === null ? '—' : new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
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
    history.value = canViewHistory.value ? await getProductHistory(productId) : null
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo cargar el detalle del producto')
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function tagsSaved(): Promise<void> {
  tagsOpen.value = false
  await load()
}
</script>

<template>
  <v-container class="py-8" fluid>
    <v-btn prepend-icon="mdi-arrow-left" variant="text" @click="router.back()">Volver</v-btn>

    <v-progress-linear v-if="loading" class="my-6" color="primary" indeterminate />
    <v-alert v-if="error" class="my-6" color="error" type="error" variant="tonal">
      {{ error }}
      <template #append><v-btn size="small" variant="text" @click="load">Reintentar</v-btn></template>
    </v-alert>

    <template v-if="product">
      <div class="d-flex flex-wrap align-center justify-space-between ga-3 my-5">
        <div>
          <h1 class="text-h4">{{ product.preferred_title || product.canonical_name || product.title }}</h1>
          <p class="text-medium-emphasis mb-0">{{ product.canonical_sku || product.sku_root || 'Sin SKU' }}</p>
        </div>
        <v-chip :color="product.canonical_product_id ? 'success' : 'warning'" variant="tonal">
          {{ product.canonical_product_id ? 'Producto canónico asignado' : 'Sin producto canónico' }}
        </v-chip>
      </div>

      <v-row>
        <v-col cols="12" md="4"><v-card><v-card-title>Stock</v-card-title><v-card-text class="text-h5">{{ product.stock }}</v-card-text></v-card></v-col>
        <v-col cols="12" md="4"><v-card><v-card-title>Precio efectivo</v-card-title><v-card-text class="text-h5">{{ formatPrice(product.sale_price) }}</v-card-text></v-card></v-col>
        <v-col cols="12" md="4"><v-card><v-card-title>Categoría</v-card-title><v-card-text class="text-h6">{{ product.category_path || 'Sin categoría' }}</v-card-text></v-card></v-col>
      </v-row>

      <v-card class="mt-6">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>Tags</span>
          <v-btn v-if="auth.isStaff" prepend-icon="mdi-pencil" size="small" variant="text" @click="tagsOpen = true">Editar</v-btn>
        </v-card-title>
        <v-card-text class="d-flex flex-wrap ga-2">
          <v-chip v-for="tag in product.tags" :key="tag.id" prepend-icon="mdi-tag-outline">{{ tag.name }}</v-chip>
          <span v-if="!product.tags.length" class="text-medium-emphasis">Sin tags</span>
        </v-card-text>
      </v-card>

      <v-card v-if="canViewHistory && history" class="mt-6">
        <v-card-title>Historial de compras</v-card-title>
        <v-data-table :headers="historyHeaders" :items="history.items">
          <template #item.gross_unit_cost="{ value }">{{ formatPrice(value) }}</template>
          <template #item.net_unit_cost="{ value }">{{ formatPrice(value) }}</template>
          <template #item.attachment_url="{ value }">
            <v-btn v-if="value" :href="value" size="small" target="_blank" variant="text">Documento</v-btn>
          </template>
          <template #no-data><div class="pa-6 text-center text-medium-emphasis">No hay compras confirmadas para este producto.</div></template>
        </v-data-table>
      </v-card>

      <v-card v-if="canViewHistory && history" class="mt-6">
        <v-card-title>Movimientos de stock por compras</v-card-title>
        <v-list v-if="history.movements.length">
          <v-list-item
            v-for="(movement, index) in history.movements"
            :key="`${movement.created_at}-${index}`"
            :subtitle="`Saldo ${movement.balance_after} · ${movement.created_at}`"
            :title="`${movement.type}: ${movement.delta > 0 ? '+' : ''}${movement.delta}`"
          />
        </v-list>
        <v-card-text v-else class="text-medium-emphasis">No hay movimientos de compras registrados.</v-card-text>
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
