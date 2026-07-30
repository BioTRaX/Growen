<!-- NG-HEADER: Nombre de archivo: CanonicalSkuEditor.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CanonicalSkuEditor.vue -->
<!-- NG-HEADER: Descripción: Edición confirmada del SKU canónico con manejo de colisiones. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { updateCanonicalSku } from '../api/products'

const props = defineProps<{
  canonicalProductId: number | null
  sku: string | null
  fallbackSku: string | null
  editable: boolean
}>()
const emit = defineEmits<{ saved: [sku: string] }>()

const editing = ref(false)
const value = ref('')
const savedSku = ref(props.sku)
const saving = ref(false)
const error = ref('')
const input = ref<{ focus?: () => void } | null>(null)
const displayedSku = computed(() => savedSku.value || props.fallbackSku || 'Sin SKU')
const normalizedValue = computed(() => value.value.trim().toUpperCase())
const canConfirm = computed(() =>
  Boolean(normalizedValue.value)
  && normalizedValue.value !== (savedSku.value || '').trim().toUpperCase()
  && !saving.value,
)

watch(() => props.sku, (sku) => {
  savedSku.value = sku
  if (!editing.value) value.value = sku || ''
})

async function startEditing(): Promise<void> {
  value.value = savedSku.value || ''
  error.value = ''
  editing.value = true
  await nextTick()
  input.value?.focus?.()
}

function cancel(): void {
  editing.value = false
  error.value = ''
  value.value = savedSku.value || ''
}

async function confirm(): Promise<void> {
  if (!props.canonicalProductId) return
  if (!normalizedValue.value) {
    error.value = 'El SKU no puede estar vacío.'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const updated = await updateCanonicalSku(props.canonicalProductId, normalizedValue.value)
    savedSku.value = updated.sku_custom
    emit('saved', updated.sku_custom)
    editing.value = false
    value.value = updated.sku_custom
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo actualizar el SKU')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="canonical-sku-editor">
    <div v-if="!editing" class="d-flex align-center ga-1">
      <span class="text-medium-emphasis">{{ displayedSku }}</span>
      <v-btn
        v-if="editable && canonicalProductId"
        aria-label="Editar SKU"
        icon="mdi-pencil"
        size="x-small"
        title="Editar SKU canónico"
        variant="text"
        @click="startEditing"
      />
    </div>
    <div v-else>
      <div class="d-flex align-start ga-1">
        <v-text-field
          ref="input"
          v-model="value"
          aria-label="Nuevo SKU canónico"
          density="compact"
          hide-details
          maxlength="32"
          placeholder="XXX_0000_YYY"
          @keydown.enter.prevent="confirm"
          @keydown.esc.prevent="cancel"
        />
        <v-btn
          :disabled="!canConfirm"
          :loading="saving"
          aria-label="Confirmar SKU"
          color="success"
          icon="mdi-check"
          size="small"
          title="Confirmar cambio"
          variant="tonal"
          @click="confirm"
        />
        <v-btn
          :disabled="saving"
          aria-label="Cancelar edición de SKU"
          icon="mdi-close"
          size="small"
          title="Cancelar"
          variant="text"
          @click="cancel"
        />
      </div>
      <div v-if="error" class="text-error text-caption mt-1" role="alert">{{ error }}</div>
      <div class="text-caption text-medium-emphasis mt-1">Formato: XXX_0000_YYY</div>
    </div>
  </div>
</template>

<style scoped>
.canonical-sku-editor {
  max-width: 390px;
}
</style>
