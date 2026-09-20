<!-- NG-HEADER: Nombre de archivo: MassCanonicalWizard.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/MassCanonicalWizard.vue -->
<!-- NG-HEADER: Descripción: Asistente de alta masiva de productos canónicos con polling persistente. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { createCanonicalBatch, getCanonicalBatchJob, previewCanonicalSkus } from '../api/products'
import { newClientRequestId } from '../composables/useMassCanonicalDraft'
import type { CanonicalBatchJobResponse, MassCanonicalDraft, ProductCategory } from '../types'
import CategoryCreatableSelect from './CategoryCreatableSelect.vue'
import MassCanonicalResults from './MassCanonicalResults.vue'
import TagCreatableSelect from './TagCreatableSelect.vue'

const props = defineProps<{
  modelValue: boolean
  draft: MassCanonicalDraft | null
  categories: ProductCategory[]
  omittedCount: number
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  completed: [job: CanonicalBatchJobResponse]
  discard: []
  categoryCreated: [category: ProductCategory]
}>()

const currentIndex = ref(0)
const loading = ref(false)
const error = ref('')
const job = ref<CanonicalBatchJobResponse | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | undefined
let pollAttempt = 0

const rows = computed(() => props.draft?.rows ?? [])
const current = computed(() => rows.value[currentIndex.value])
const allValid = computed(() => rows.value.length > 0 && rows.value.every((row) =>
  row.name.trim() && row.categoryId && row.subcategoryId &&
  props.categories.some((category) => category.id === row.categoryId && category.kind === 'category') &&
  props.categories.some((category) => category.id === row.subcategoryId && category.kind === 'subcategory'),
))
const terminal = computed(() => job.value && ['COMPLETED', 'PARTIAL', 'FAILED'].includes(job.value.status))

function setStep(step: number): void {
  if (props.draft) props.draft.step = step
}

function taxonomyChanged(): void {
  if (!current.value) return
  current.value.previewSku = null
}

function mergedTags(row: MassCanonicalDraft['rows'][number]): string[] {
  const tags = new Map<string, string>()
  ;[...(props.draft?.commonTagNames ?? []), ...row.tagNames].forEach((name) => {
    const clean = name.trim().replace(/\s+/g, ' ')
    if (clean) tags.set(clean.toLocaleLowerCase('es'), clean)
  })
  return [...tags.values()]
}

async function refreshPreviews(): Promise<boolean> {
  if (!allValid.value) {
    error.value = 'Completá nombre, categoría y subcategoría en todos los productos.'
    return false
  }
  loading.value = true
  error.value = ''
  try {
    const response = await previewCanonicalSkus(rows.value)
    response.items.forEach((preview) => {
      if (rows.value[preview.position]) rows.value[preview.position].previewSku = preview.sku
    })
    return true
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudieron calcular los SKU provisionales')
    return false
  } finally {
    loading.value = false
  }
}

async function review(): Promise<void> {
  if (await refreshPreviews()) setStep(3)
}

function schedulePoll(): void {
  if (!props.draft?.jobId || terminal.value) return
  const delay = pollAttempt < 2 ? 1000 : pollAttempt < 5 ? 2000 : 5000
  pollTimer = setTimeout(() => void poll(), delay)
}

async function poll(): Promise<void> {
  if (!props.draft?.jobId) return
  try {
    job.value = await getCanonicalBatchJob(props.draft.jobId)
    pollAttempt += 1
    if (terminal.value && job.value) emit('completed', job.value)
    else schedulePoll()
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo consultar el progreso. Podés reintentar sin reenviar el lote.')
  }
}

async function submit(): Promise<void> {
  if (!props.draft || !allValid.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await createCanonicalBatch(
      props.draft.clientRequestId,
      rows.value.map((row) => ({ ...row, tagNames: mergedTags(row) })),
    )
    props.draft.jobId = response.job_id
    setStep(4)
    pollAttempt = 0
    await poll()
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo enviar el lote')
  } finally {
    loading.value = false
  }
}

function retryFailed(): void {
  if (!props.draft || !job.value) return
  const failed = new Set(job.value.items.filter((item) => item.status === 'FAILED').map((item) => item.position))
  props.draft.rows = props.draft.rows.filter((_row, index) => failed.has(index)).map((row) => ({ ...row, previewSku: null }))
  props.draft.clientRequestId = newClientRequestId()
  props.draft.jobId = null
  job.value = null
  currentIndex.value = 0
  setStep(2)
}

async function retryUnprocessed(): Promise<void> {
  if (!props.draft || !job.value || job.value.status !== 'FAILED' || job.value.processed_items !== 0) return
  props.draft.jobId = null
  job.value = null
  pollAttempt = 0
  setStep(3)
  await submit()
}

function close(): void {
  if (terminal.value) emit('discard')
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (open) => {
  if (!open) return
  error.value = ''
  if (props.draft?.jobId) {
    setStep(4)
    void poll()
  }
})

onBeforeUnmount(() => pollTimer && clearTimeout(pollTimer))
</script>

<template>
  <v-dialog :model-value="modelValue" fullscreen persistent @update:model-value="emit('update:modelValue', $event)">
    <v-card v-if="draft">
      <v-toolbar color="primary">
        <v-toolbar-title>Alta masiva de productos canónicos</v-toolbar-title>
        <v-btn icon="mdi-close" @click="close" />
      </v-toolbar>
      <v-card-text class="mx-auto w-100" style="max-width: 1200px">
        <v-stepper :model-value="draft.step" alt-labels class="mb-5">
          <v-stepper-header>
            <v-stepper-item :value="1" title="Preparar" />
            <v-divider /><v-stepper-item :value="2" title="Completar" />
            <v-divider /><v-stepper-item :value="3" title="Revisar" />
            <v-divider /><v-stepper-item :value="4" title="Procesar" />
          </v-stepper-header>
        </v-stepper>

        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>

        <template v-if="draft.step === 1">
          <h2 class="text-h5 mb-3">Productos incluidos</h2>
          <p>Se crearán {{ rows.length }} canónico(s) desde productos de proveedor.</p>
          <v-alert v-if="omittedCount" class="my-3" type="warning" variant="tonal">
            Se omitieron {{ omittedCount }} fila(s) ya canonizadas o sin oferta de proveedor.
          </v-alert>
          <TagCreatableSelect v-model="draft.commonTagNames" class="my-4" label="Tags comunes para todo el lote (opcional)" />
          <v-list border><v-list-item v-for="row in rows" :key="row.sourceProductId" :title="row.sourceName" :subtitle="row.supplierName" /></v-list>
        </template>

        <template v-else-if="draft.step === 2 && current">
          <div class="d-flex justify-space-between align-center mb-4">
            <h2 class="text-h5">Producto {{ currentIndex + 1 }} de {{ rows.length }}</h2>
            <v-chip>{{ current.sourceName }}</v-chip>
          </div>
          <v-row>
            <v-col cols="12"><v-text-field v-model="current.name" label="Nombre" /></v-col>
            <v-col cols="12" md="6">
              <CategoryCreatableSelect
                :categories="categories"
                kind="category"
                label="Categoría"
                :model-value="current.categoryId"
                @created="emit('categoryCreated', $event)"
                @update:model-value="current.categoryId = $event; taxonomyChanged()"
              />
            </v-col>
            <v-col cols="12" md="6">
              <CategoryCreatableSelect
                v-model="current.subcategoryId"
                :categories="categories"
                kind="subcategory"
                label="Subcategoría"
                @created="emit('categoryCreated', $event)"
                @update:model-value="taxonomyChanged"
              />
            </v-col>
            <v-col cols="12" md="6"><v-text-field v-model="current.brand" clearable label="Marca (opcional)" /></v-col>
            <v-col cols="12" md="6"><v-text-field :model-value="current.previewSku || 'Se calculará al revisar'" disabled label="SKU provisional" /></v-col>
            <v-col cols="12"><TagCreatableSelect v-model="current.tagNames" label="Tags particulares (opcional)" /></v-col>
          </v-row>
          <div class="d-flex justify-space-between">
            <v-btn :disabled="currentIndex === 0" variant="text" @click="currentIndex--">Anterior</v-btn>
            <v-btn v-if="currentIndex < rows.length - 1" color="primary" @click="currentIndex++">Siguiente</v-btn>
            <v-btn v-else color="primary" :loading="loading" @click="review">Revisar lote</v-btn>
          </div>
        </template>

        <template v-else-if="draft.step === 3">
          <h2 class="text-h5 mb-3">Revisión final</h2>
          <v-alert class="mb-4" type="info" variant="tonal">La secuencia es provisional. El backend asignará el SKU definitivo de forma transaccional.</v-alert>
          <v-table><thead><tr><th>Nombre</th><th>Categoría</th><th>Tags</th><th>Marca</th><th>SKU provisional</th></tr></thead><tbody>
            <tr v-for="row in rows" :key="row.sourceProductId"><td>{{ row.name }}</td><td>{{ categories.find(c => c.id === row.categoryId)?.name }} › {{ categories.find(c => c.id === row.subcategoryId)?.name }}</td><td>{{ mergedTags(row).join(', ') || '—' }}</td><td>{{ row.brand || '—' }}</td><td><code>{{ row.previewSku }}</code></td></tr>
          </tbody></v-table>
        </template>

        <template v-else>
          <h2 class="text-h5 mb-3">Procesamiento</h2>
          <MassCanonicalResults :job="job" :rows="rows" />
        </template>
      </v-card-text>
      <v-card-actions class="justify-end pa-4">
        <v-btn v-if="draft.step < 4" color="error" variant="text" @click="emit('discard')">Descartar borrador</v-btn>
        <v-btn v-if="draft.step === 1" color="primary" @click="setStep(2)">Completar datos</v-btn>
        <v-btn v-if="draft.step === 3" variant="text" @click="setStep(2)">Corregir</v-btn>
        <v-btn v-if="draft.step === 3" color="primary" :disabled="!allValid" :loading="loading" @click="submit">Crear {{ rows.length }} canónico(s)</v-btn>
        <v-btn v-if="draft.step === 4 && job?.status === 'FAILED' && job.processed_items === 0" color="warning" :loading="loading" @click="retryUnprocessed">Reintentar lote</v-btn>
        <v-btn v-if="draft.step === 4 && job?.error_count" color="warning" @click="retryFailed">Corregir fallidos</v-btn>
        <v-btn v-if="draft.step === 4 && terminal" color="primary" @click="close">Cerrar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
