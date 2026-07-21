<!-- NG-HEADER: Nombre de archivo: ProductStockDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductStockDialog.vue -->
<!-- NG-HEADER: Descripción: Edición validada de stock para Productos Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import { updateProductStock } from '../api/products'
import { isValidStock } from '../productValidation'
import type { ProductListItem } from '../types'

const props = defineProps<{ modelValue: boolean; product: ProductListItem | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [stock: number] }>()
const stock = ref(0)
const loading = ref(false)
const error = ref('')
const valid = computed(() => isValidStock(stock.value))

watch(() => props.modelValue, (open) => {
  if (!open || !props.product) return
  stock.value = props.product.stock
  error.value = ''
})

async function save(): Promise<void> {
  if (!props.product || !valid.value) return
  loading.value = true
  error.value = ''
  try {
    const result = await updateProductStock(props.product.product_id, stock.value, props.product.stock)
    emit('saved', result.stock)
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo actualizar el stock')
  } finally { loading.value = false }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="440" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Editar stock</v-card-title>
      <v-card-subtitle>{{ product?.preferred_name || product?.name }}</v-card-subtitle>
      <v-card-text>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <v-text-field v-model.number="stock" autofocus label="Stock" min="0" step="0.01" type="number" />
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn variant="text" @click="emit('update:modelValue', false)">Cancelar</v-btn>
        <v-btn color="primary" :disabled="!valid" :loading="loading" @click="save">Guardar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
