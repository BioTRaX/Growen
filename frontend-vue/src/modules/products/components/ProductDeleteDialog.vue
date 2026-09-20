<!-- NG-HEADER: Nombre de archivo: ProductDeleteDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductDeleteDialog.vue -->
<!-- NG-HEADER: Descripción: Confirmación y resumen del borrado protegido de Productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import { deleteProducts } from '../api/products'
import type { ProductDeleteResult, ProductListItem } from '../types'

const props = defineProps<{ modelValue: boolean; products: ProductListItem[] }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  deleted: [result: ProductDeleteResult]
}>()
const loading = ref(false)
const error = ref('')

watch(() => props.modelValue, (open) => { if (open) error.value = '' })

async function confirm(): Promise<void> {
  const ids = props.products.map((product) => product.product_id)
  if (!ids.length) return
  loading.value = true
  error.value = ''
  try {
    const result = await deleteProducts(ids)
    emit('deleted', result)
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudieron borrar los productos')
  } finally { loading.value = false }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="560" persistent @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Confirmar borrado</v-card-title>
      <v-card-text>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <p>Vas a solicitar el borrado permanente de <strong>{{ products.length }}</strong> producto(s).</p>
        <v-alert v-if="products.some((product) => product.stock > 0)" class="mb-4" type="warning" variant="tonal">
          La selección contiene productos con stock. El backend los bloqueará y sólo eliminará los productos permitidos.
        </v-alert>
        <p class="text-medium-emphasis mb-0">
          También se bloquearán productos referenciados por compras. Esta acción no se puede deshacer.
        </p>
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn :disabled="loading" variant="text" @click="emit('update:modelValue', false)">Cancelar</v-btn>
        <v-btn color="error" :loading="loading" @click="confirm">Borrar productos</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
