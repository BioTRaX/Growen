<!-- NG-HEADER: Nombre de archivo: CanonicalNameEditor.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CanonicalNameEditor.vue -->
<!-- NG-HEADER: Descripción: Edición en línea del nombre canónico de producto con validación y confirmación. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { updateCanonicalName, updateProductTitle } from '../api/products'

const props = defineProps<{
  canonicalProductId: number | null
  productId?: number | null
  name: string | null
  editable: boolean
}>()

const emit = defineEmits<{ saved: [name: string] }>()

const editing = ref(false)
const value = ref('')
const savedName = ref(props.name)
const saving = ref(false)
const error = ref('')
const input = ref<{ focus?: () => void } | null>(null)

const displayName = computed(() => savedName.value || 'Sin nombre')
const normalizedValue = computed(() => value.value.trim())
const canConfirm = computed(() =>
  Boolean(normalizedValue.value)
  && normalizedValue.value !== (savedName.value || '').trim()
  && !saving.value,
)

watch(() => props.name, (name) => {
  savedName.value = name
  if (!editing.value) value.value = name || ''
})

async function startEditing(): Promise<void> {
  value.value = savedName.value || ''
  error.value = ''
  editing.value = true
  await nextTick()
  input.value?.focus?.()
}

function cancel(): void {
  editing.value = false
  error.value = ''
  value.value = savedName.value || ''
}

async function confirm(): Promise<void> {
  if (!normalizedValue.value) {
    error.value = 'El nombre no puede estar vacío.'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const newName = normalizedValue.value
    let committedName = newName
    if (props.canonicalProductId) {
      const res = await updateCanonicalName(props.canonicalProductId, newName)
      committedName = res.name
    } else if (props.productId) {
      await updateProductTitle(props.productId, newName)
    } else {
      throw new Error('No hay un producto disponible para actualizar')
    }
    savedName.value = committedName
    emit('saved', committedName)
    editing.value = false
    value.value = committedName
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo actualizar el nombre del producto')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="canonical-name-editor">
    <div v-if="!editing" class="d-flex align-center ga-2">
      <h1 class="text-h4 mb-0">{{ displayName }}</h1>
      <v-btn
        v-if="editable && (canonicalProductId || productId)"
        aria-label="Editar nombre canónico"
        icon="mdi-pencil"
        size="small"
        title="Editar nombre canónico"
        variant="text"
        @click="startEditing"
      />
    </div>
    <div v-else class="my-1">
      <div class="d-flex align-start ga-2">
        <v-text-field
          ref="input"
          v-model="value"
          aria-label="Nuevo nombre canónico"
          density="compact"
          hide-details
          maxlength="200"
          placeholder="Nombre canónico del producto"
          @keydown.enter.prevent="confirm"
          @keydown.esc.prevent="cancel"
        />
        <v-btn
          :disabled="!canConfirm"
          :loading="saving"
          aria-label="Confirmar nombre"
          color="success"
          icon="mdi-check"
          size="small"
          title="Confirmar cambio"
          variant="tonal"
          @click="confirm"
        />
        <v-btn
          :disabled="saving"
          aria-label="Cancelar edición de nombre"
          icon="mdi-close"
          size="small"
          title="Cancelar"
          variant="text"
          @click="cancel"
        />
      </div>
      <div v-if="error" class="text-error text-caption mt-1" role="alert">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.canonical-name-editor {
  max-width: 650px;
}
</style>
