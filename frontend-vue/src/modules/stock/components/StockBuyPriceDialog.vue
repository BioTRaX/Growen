<!-- NG-HEADER: Nombre de archivo: StockBuyPriceDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/stock/components/StockBuyPriceDialog.vue -->
<!-- NG-HEADER: Descripción: Edición del precio de compra desde Stock Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import { updateSupplierBuyPrice } from '../../products/api/products'
import { parsePositivePrice } from '../../products/productValidation'
import type { ProductListItem } from '../../products/types'
const props = defineProps<{ modelValue: boolean; product: ProductListItem | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [price: number] }>()
const value = ref(''); const loading = ref(false); const error = ref('')
const valid = computed(() => parsePositivePrice(value.value) !== null && Boolean(props.product?.supplier_item_id))
watch(() => props.modelValue, open => { if (open) { value.value = String(props.product?.precio_compra ?? ''); error.value = '' } })
async function save(): Promise<void> {
  const parsed = parsePositivePrice(value.value)
  if (parsed === null || !props.product?.supplier_item_id) return
  loading.value = true; error.value = ''
  try { await updateSupplierBuyPrice(props.product.supplier_item_id, parsed); emit('saved', parsed); emit('update:modelValue', false) }
  catch (cause) { error.value = getHttpErrorMessage(cause, 'No se pudo actualizar el precio de compra') }
  finally { loading.value = false }
}
</script>
<template><v-dialog :model-value="modelValue" max-width="460" @update:model-value="emit('update:modelValue', $event)"><v-card>
  <v-card-title>Editar precio de compra</v-card-title><v-card-subtitle>{{ product?.preferred_name || product?.name }}</v-card-subtitle>
  <v-card-text><v-alert v-if="error" class="mb-3" type="error" variant="tonal">{{ error }}</v-alert><v-text-field v-model="value" autofocus inputmode="decimal" label="Precio de compra" prefix="$" /></v-card-text>
  <v-card-actions class="justify-end"><v-btn @click="emit('update:modelValue', false)">Cancelar</v-btn><v-btn color="primary" :disabled="!valid" :loading="loading" @click="save">Guardar</v-btn></v-card-actions>
</v-card></v-dialog></template>
