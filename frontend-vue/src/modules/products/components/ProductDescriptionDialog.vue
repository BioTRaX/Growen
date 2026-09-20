<!-- NG-HEADER: Nombre de archivo: ProductDescriptionDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductDescriptionDialog.vue -->
<!-- NG-HEADER: Descripción: Diálogo para la edición manual de la descripción de producto con editor y vista previa. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { updateCanonicalDescription, updateProductDescription } from '../api/products'
import { formatDescriptionToHtml } from '../productDescription'

const props = defineProps<{
  modelValue: boolean
  canonicalProductId?: number | null
  productId?: number | null
  descriptionHtml?: string | null
  productTitle?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [payload: { descriptionHtml: string; contentRevision?: number }]
}>()

const activeTab = ref<'edit' | 'preview'>('edit')
const content = ref('')
const loading = ref(false)
const error = ref('')

const previewHtml = computed(() => formatDescriptionToHtml(content.value))

const hasChanges = computed(() => {
  const current = (props.descriptionHtml || '').trim()
  const candidate = formatDescriptionToHtml(content.value)
  return candidate !== current
})

watch(() => props.modelValue, (open) => {
  if (!open) return
  content.value = props.descriptionHtml || ''
  activeTab.value = 'edit'
  error.value = ''
})

function close(): void {
  if (!loading.value) {
    emit('update:modelValue', false)
  }
}

function insertTag(openTag: string, closeTag: string): void {
  content.value = `${content.value}${openTag}${closeTag}`
}

function convertToParagraphs(): void {
  content.value = formatDescriptionToHtml(content.value)
}

async function save(): Promise<void> {
  const finalHtml = formatDescriptionToHtml(content.value)
  loading.value = true
  error.value = ''
  try {
    let contentRevision: number | undefined
    if (props.canonicalProductId) {
      const res = await updateCanonicalDescription(props.canonicalProductId, finalHtml)
      contentRevision = res.content_revision
    } else if (props.productId) {
      await updateProductDescription(props.productId, finalHtml)
    } else {
      throw new Error('No hay un identificador de producto disponible para actualizar')
    }

    emit('saved', { descriptionHtml: finalHtml, contentRevision })
    emit('update:modelValue', false)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo guardar la descripción del producto')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="840" persistent @update:model-value="!$event && close()">
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between pb-1">
        <span>Editar descripción</span>
        <v-btn icon="mdi-close" variant="text" size="small" :disabled="loading" @click="close" />
      </v-card-title>
      <v-card-subtitle v-if="productTitle" class="pt-0">
        {{ productTitle }}
      </v-card-subtitle>

      <v-tabs v-model="activeTab" class="px-4">
        <v-tab value="edit" prepend-icon="mdi-pencil">Editor</v-tab>
        <v-tab value="preview" prepend-icon="mdi-eye">Vista previa</v-tab>
      </v-tabs>

      <v-divider />

      <v-card-text class="pt-4">
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>

        <v-window v-model="activeTab">
          <v-window-item value="edit">
            <div class="d-flex flex-wrap ga-2 mb-3">
              <v-btn size="x-small" variant="tonal" prepend-icon="mdi-format-bold" @click="insertTag('<strong>', '</strong>')">
                Negrita
              </v-btn>
              <v-btn size="x-small" variant="tonal" prepend-icon="mdi-format-paragraph" @click="insertTag('<p>', '</p>')">
                Párrafo
              </v-btn>
              <v-btn size="x-small" variant="tonal" prepend-icon="mdi-format-list-bulleted" @click="insertTag('<ul>\n  <li>', '</li>\n</ul>')">
                Lista
              </v-btn>
              <v-btn size="x-small" variant="tonal" prepend-icon="mdi-auto-fix" @click="convertToParagraphs">
                Formatear a &lt;p&gt;
              </v-btn>
            </div>

            <v-textarea
              v-model="content"
              autofocus
              auto-grow
              rows="9"
              variant="outlined"
              label="Contenido de la descripción"
              placeholder="Escribí la descripción del producto. Podés usar texto con párrafos o etiquetas HTML (<p>, <strong>, <ul>, etc.)."
              persistent-hint
              hint="El texto plano se convertirá automáticamente en párrafos <p>...</p> al guardar."
            />
          </v-window-item>

          <v-window-item value="preview">
            <div class="preview-box pa-4 rounded border">
              <div v-if="previewHtml" class="product-description" v-html="previewHtml" />
              <div v-else class="text-medium-emphasis">No hay contenido para previsualizar.</div>
            </div>
          </v-window-item>
        </v-window>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn :disabled="loading" variant="text" @click="close">Cancelar</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="loading"
          :disabled="!hasChanges || loading"
          @click="save"
        >
          Guardar descripción
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.preview-box {
  min-height: 200px;
  background-color: rgba(var(--v-theme-surface-variant), 0.05);
}
.product-description :deep(p) {
  margin-bottom: 0.75rem;
}
.product-description :deep(ul),
.product-description :deep(ol) {
  padding-left: 1.5rem;
  margin-bottom: 0.75rem;
}
</style>
