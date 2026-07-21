<!-- NG-HEADER: Nombre de archivo: TagManagementDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/TagManagementDialog.vue -->
<!-- NG-HEADER: Descripción: Gestión individual y asignación masiva aditiva de tags de productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { assignProductTags, bulkAssignProductTags, removeProductTag } from '../api/products'
import type { ProductTag } from '../types'
import TagCreatableSelect from './TagCreatableSelect.vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  productIds: number[]
  currentTags?: ProductTag[]
  bulk?: boolean
}>(), { currentTags: () => [], bulk: false })
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [tagNames: string[]]
}>()

const selected = ref<string[]>([])
const loading = ref(false)
const error = ref('')

watch(() => props.modelValue, (open) => {
  if (!open) return
  selected.value = props.bulk ? [] : props.currentTags.map((tag) => tag.name)
  error.value = ''
})

async function save(): Promise<void> {
  if (!props.productIds.length || (props.bulk && !selected.value.length) || loading.value) return
  loading.value = true
  error.value = ''
  try {
    if (props.bulk) {
      await bulkAssignProductTags(props.productIds, selected.value)
    } else {
      const productId = props.productIds[0]
      if (selected.value.length) await assignProductTags(productId, selected.value)
      const retained = new Set(selected.value.map((name) => name.toLocaleLowerCase('es')))
      await Promise.all(props.currentTags.filter((tag) => !retained.has(tag.name.toLocaleLowerCase('es')))
        .map((tag) => removeProductTag(productId, tag.id)))
    }
    emit('saved', selected.value)
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudieron guardar los tags')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="680" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>{{ bulk ? `Agregar tags a ${productIds.length} productos` : 'Editar tags' }}</v-card-title>
      <v-card-text>
        <v-alert v-if="bulk" class="mb-4" type="info" variant="tonal">La operación es aditiva: conserva los tags actuales.</v-alert>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <TagCreatableSelect v-model="selected" />
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn :disabled="loading" variant="text" @click="emit('update:modelValue', false)">Cancelar</v-btn>
        <v-btn color="primary" :disabled="bulk && !selected.length" :loading="loading" @click="save">Guardar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
