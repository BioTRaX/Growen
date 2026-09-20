<!-- NG-HEADER: Nombre de archivo: StructuredProductData.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/StructuredProductData.vue -->
<!-- NG-HEADER: Descripción: Presentación recursiva y legible de datos estructurados de producto. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ name: 'StructuredProductData' })

const props = defineProps<{ value: unknown }>()

const labels: Record<string, string> = {
  additional_recommendations: 'Recomendaciones adicionales',
  base_diameter_cm: 'Diámetro de base (cm)',
  capacity_l: 'Capacidad (L)',
  depth_cm: 'Profundidad (cm)',
  diameter_cm: 'Diámetro (cm)',
  diameter_top_cm: 'Diámetro superior (cm)',
  dimensions: 'Dimensiones',
  dimensions_alternative: 'Dimensiones alternativas',
  drainage: 'Drenaje',
  height_cm: 'Altura (cm)',
  instructions: 'Instrucciones',
  material: 'Material',
  recommendations: 'Recomendaciones',
  reusable: 'Reutilizable',
  steps: 'Pasos',
  use: 'Uso',
  usage: 'Uso',
  width_cm: 'Ancho (cm)',
}
const hiddenMetadataKeys = new Set([
  'evidence',
  'provenance',
  'source',
  'source_note',
  'source_url',
  'sources',
])

const isArray = computed(() => Array.isArray(props.value))
const isRecord = computed(() => props.value !== null && typeof props.value === 'object' && !isArray.value)
const entries = computed(() => isRecord.value
  ? Object.entries(props.value as Record<string, unknown>).filter(([key]) => !hiddenMetadataKeys.has(key))
  : [])
const isEmpty = computed(() => props.value === null || props.value === undefined || props.value === ''
  || (isArray.value && (props.value as unknown[]).length === 0)
  || (isRecord.value && entries.value.length === 0))

function fieldLabel(key: string): string {
  if (labels[key]) return labels[key]
  const words = key.replaceAll('_', ' ').trim()
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : key
}

function scalarText(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  return String(value)
}
</script>

<template>
  <span v-if="isEmpty" class="text-medium-emphasis">—</span>
  <ul v-else-if="isArray" class="structured-list">
    <li v-for="(item, index) in (value as unknown[])" :key="index">
      <StructuredProductData :value="item" />
    </li>
  </ul>
  <dl v-else-if="isRecord" class="structured-fields">
    <div v-for="([key, item]) in entries" :key="key" class="structured-field">
      <dt>{{ fieldLabel(key) }}</dt>
      <dd><StructuredProductData :value="item" /></dd>
    </div>
  </dl>
  <span v-else>{{ scalarText(value) }}</span>
</template>

<style scoped>
.structured-fields { margin: 0; }
.structured-field { padding: 0.45rem 0; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.structured-field:last-child { border-bottom: 0; }
.structured-field > dt { color: rgba(var(--v-theme-on-surface), 0.68); font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em; }
.structured-field > dd { margin: 0.15rem 0 0; }
.structured-field .structured-fields { margin: 0.25rem 0 0.1rem 0.75rem; }
.structured-list { margin: 0.2rem 0 0; padding-left: 1.25rem; }
.structured-list > li { margin-bottom: 0.35rem; }
.structured-list > li:last-child { margin-bottom: 0; }
</style>
