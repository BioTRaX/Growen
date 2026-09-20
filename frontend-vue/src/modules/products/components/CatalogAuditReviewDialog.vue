<!-- NG-HEADER: Nombre de archivo: CatalogAuditReviewDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CatalogAuditReviewDialog.vue -->
<!-- NG-HEADER: Descripción: Confirmación administrada de revisiones del auditor desde Productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { resolveCatalogAuditItem } from '../../catalog-audit/api/catalogAudit'
import type { ProductListItem } from '../types'

const props = defineProps<{ modelValue: boolean; product: ProductListItem | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  resolved: [product: ProductListItem]
}>()

const note = ref('')
const loading = ref(false)
const error = ref('')
const canConfirm = computed(() => note.value.trim().length >= 3 && !loading.value)

watch(() => [props.modelValue, props.product?.product_id], ([open]) => {
  if (open) {
    note.value = ''
    error.value = ''
  }
})

function close(): void {
  if (!loading.value) emit('update:modelValue', false)
}

async function confirm(): Promise<void> {
  const product = props.product
  const normalizedNote = note.value.trim()
  if (!product?.catalog_audit_run_id || !product.catalog_audit_item_id) {
    error.value = 'No se encontraron las coordenadas de la revisión'
    return
  }
  if (normalizedNote.length < 3) return

  loading.value = true
  error.value = ''
  try {
    await resolveCatalogAuditItem(product.catalog_audit_run_id, product.catalog_audit_item_id, {
      action: 'accept_exception',
      note: normalizedNote,
    })
    emit('resolved', product)
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo aceptar la revisión')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="560" persistent @update:model-value="!$event && close()">
    <v-card>
      <v-card-title>Aceptar revisión del auditor</v-card-title>
      <v-card-text>
        <p class="mb-4">
          Confirmá que <strong>{{ product?.preferred_name || product?.canonical_name || product?.name }}</strong>
          fue revisado y es correcto. Esta acción no aplica correcciones sugeridas por IA.
        </p>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <v-textarea
          v-model="note"
          autofocus
          label="Nota de revisión"
          persistent-hint
          hint="Mínimo 3 caracteres. No incluyas información sensible."
          rows="3"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="loading" variant="text" @click="close">Cancelar</v-btn>
        <v-btn color="primary" :disabled="!canConfirm" :loading="loading" @click="confirm">Aceptar revisión</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
