<!-- NG-HEADER: Nombre de archivo: ShortageReportDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/stock/components/ShortageReportDialog.vue -->
<!-- NG-HEADER: Descripción: Alta decimal de faltantes con búsqueda remota cancelable. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { listProducts } from '../../products/api/products'
import type { ProductListItem } from '../../products/types'
import { createShortage } from '../api/stock'
import { SHORTAGE_REASON_LABELS, type ShortageReason } from '../types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; created: [message: string] }>()
const query = ref('')
const products = ref<ProductListItem[]>([])
const selected = ref<ProductListItem | null>(null)
const quantity = ref<number | null>(null)
const reason = ref<ShortageReason>('UNKNOWN')
const observation = ref('')
const searching = ref(false)
const submitting = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined
let searchSequence = 0

const reasonItems = Object.entries(SHORTAGE_REASON_LABELS).map(([value, title]) => ({ value, title }))
const validQuantity = computed(() => {
  if (quantity.value === null || !Number.isFinite(quantity.value) || quantity.value <= 0) return false
  return Math.abs(quantity.value * 100 - Math.round(quantity.value * 100)) < 1e-8
})
const resultingStock = computed(() => selected.value && validQuantity.value ? selected.value.stock - Number(quantity.value) : null)

watch(() => props.modelValue, (open) => {
  if (open) return
  reset()
})

watch(query, (value) => {
  if (selected.value && value !== productLabel(selected.value)) selected.value = null
  clearTimeout(timer)
  controller?.abort()
  products.value = []
  if (!props.modelValue || value.trim().length < 2 || selected.value) return
  timer = setTimeout(() => { void search(value.trim()) }, 300)
})

async function search(value: string): Promise<void> {
  controller = new AbortController()
  const current = ++searchSequence
  searching.value = true
  try {
    const result = await listProducts({ q: value, supplier_id: null, category_id: null, stock: '', recent: '', type: 'all', page: 1, page_size: 50 }, controller.signal)
    if (current === searchSequence) products.value = result.items
  } catch (cause) {
    if (current !== searchSequence) return
    const message = getHttpErrorMessage(cause, 'No se pudo buscar productos')
    if (message) error.value = message
  } finally {
    if (current === searchSequence) searching.value = false
  }
}

function productLabel(product: ProductListItem): string {
  const sku = product.canonical_sku || product.first_variant_sku
  return sku ? `${product.preferred_name || product.name} · ${sku}` : product.preferred_name || product.name
}

function selectProduct(product: ProductListItem | null): void {
  selected.value = product
  if (product) query.value = productLabel(product)
}

function reset(): void {
  clearTimeout(timer)
  controller?.abort()
  query.value = ''
  products.value = []
  selected.value = null
  quantity.value = null
  reason.value = 'UNKNOWN'
  observation.value = ''
  error.value = ''
}

async function save(): Promise<void> {
  if (!selected.value || !validQuantity.value || quantity.value === null) return
  if (resultingStock.value !== null && resultingStock.value < 0 && !window.confirm(`El saldo quedará negativo (${resultingStock.value.toFixed(2)}). ¿Deseas continuar?`)) return
  submitting.value = true
  error.value = ''
  try {
    const result = await createShortage({ product_id: selected.value.product_id, quantity: quantity.value, reason: reason.value, observation: observation.value.trim() || undefined })
    emit('created', result.warning ? `Faltante registrado. ${result.warning}` : 'Faltante registrado correctamente')
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo registrar el faltante')
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => { clearTimeout(timer); controller?.abort() })
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="600" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Reportar faltante</v-card-title>
      <v-card-text>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <v-autocomplete
          v-model:search="query"
          :items="products"
          :loading="searching"
          :model-value="selected"
          :no-data-text="query.trim().length < 2 ? 'Escribí al menos 2 caracteres' : 'Sin resultados'"
          clearable
          item-value="product_id"
          label="Producto"
          placeholder="Buscar por nombre o SKU"
          return-object
          @update:model-value="selectProduct($event)"
        >
          <template #item="{ props: itemProps, item }"><v-list-item v-bind="itemProps" :subtitle="`Stock: ${Number(item.raw.stock).toFixed(2)}`" :title="productLabel(item.raw)" /></template>
        </v-autocomplete>
        <v-alert v-if="resultingStock !== null && resultingStock < 0" class="mb-4" type="warning" variant="tonal">El saldo quedará negativo: {{ resultingStock.toFixed(2) }}.</v-alert>
        <v-text-field v-model.number="quantity" label="Cantidad" min="0.01" step="0.01" type="number" :error-messages="quantity !== null && !validQuantity ? ['Usá una cantidad positiva con hasta dos decimales'] : []" />
        <v-select v-model="reason" :items="reasonItems" label="Motivo" />
        <v-textarea v-model="observation" counter="1000" label="Observación" maxlength="1000" rows="3" />
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn variant="text" @click="emit('update:modelValue', false)">Cancelar</v-btn>
        <v-btn color="primary" :disabled="!selected || !validQuantity" :loading="submitting" @click="save">Registrar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
