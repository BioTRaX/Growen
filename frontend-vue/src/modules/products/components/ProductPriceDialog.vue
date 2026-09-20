<!-- NG-HEADER: Nombre de archivo: ProductPriceDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductPriceDialog.vue -->
<!-- NG-HEADER: Descripción: Edición de precio efectivo canónico o de proveedor en Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import { updateCanonicalSalePrice, updateSupplierSalePrice } from '../api/products'
import { effectiveSalePrice } from '../productPresentation'
import { parsePositivePrice } from '../productValidation'
import type { ProductListItem } from '../types'

const props = defineProps<{ modelValue: boolean; product: ProductListItem | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [price: number] }>()
const price = ref('')
const loading = ref(false)
const error = ref('')

const valid = computed(() => parsePositivePrice(price.value) !== null)
const priceScope = computed(() => props.product?.canonical_product_id ? 'producto canónico' : 'oferta del proveedor')

watch(() => props.modelValue, (open) => {
  if (!open || !props.product) return
  price.value = String(effectiveSalePrice(props.product) ?? '')
  error.value = ''
})

async function save(): Promise<void> {
  const value = parsePositivePrice(price.value)
  if (!props.product || value === null) return
  loading.value = true
  error.value = ''
  try {
    if (props.product.canonical_product_id) {
      await updateCanonicalSalePrice(props.product.canonical_product_id, value)
    } else if (props.product.supplier_item_id) {
      await updateSupplierSalePrice(props.product.supplier_item_id, value)
    } else {
      throw new Error('El producto no tiene una oferta editable')
    }
    emit('saved', value)
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = cause instanceof Error && cause.message === 'El producto no tiene una oferta editable'
      ? cause.message
      : getHttpErrorMessage(cause, 'No se pudo actualizar el precio de venta')
  } finally { loading.value = false }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="460" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Editar precio de venta</v-card-title>
      <v-card-subtitle>{{ product?.preferred_name || product?.name }}</v-card-subtitle>
      <v-card-text>
        <v-alert class="mb-4" type="info" variant="tonal">Se actualizará el {{ priceScope }}.</v-alert>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <v-text-field v-model="price" autofocus inputmode="decimal" label="Precio de venta" prefix="$" />
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn variant="text" @click="emit('update:modelValue', false)">Cancelar</v-btn>
        <v-btn color="primary" :disabled="!valid" :loading="loading" @click="save">Guardar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
