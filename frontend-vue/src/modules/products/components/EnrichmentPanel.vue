<!-- NG-HEADER: Nombre de archivo: EnrichmentPanel.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/EnrichmentPanel.vue -->
<!-- NG-HEADER: Descripción: Generación, progreso y revisión de propuestas Enrich v2. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref } from 'vue'

import type { EnrichmentJob, EnrichmentScope } from '../types'

const props = defineProps<{
  job: EnrichmentJob | null
  loading: boolean
  error: string
}>()
const emit = defineEmits<{
  start: [scope: EnrichmentScope]
  apply: [fields: string[]]
  discard: []
}>()
const selected = ref<string[]>([])
const proposalFields = computed(() => Object.keys(props.job?.proposal ?? {}).filter(
  (field) => !props.job?.applied_fields.includes(field),
))
const isActive = computed(() => ['queued', 'running'].includes(props.job?.status ?? ''))

function label(field: string): string {
  return ({
    description_html: 'Descripción',
    weight_kg: 'Peso',
    height_cm: 'Alto',
    width_cm: 'Ancho',
    depth_cm: 'Profundidad',
    technical_specs: 'Especificaciones',
    usage_instructions: 'Instrucciones',
  } as Record<string, string>)[field] ?? field
}
</script>

<template>
  <v-card>
    <v-card-title class="d-flex flex-wrap align-center justify-space-between ga-2">
      <span>Enrich v2</span>
      <v-menu>
        <template #activator="{ props: menuProps }">
          <v-btn v-bind="menuProps" :disabled="loading || isActive" color="primary" prepend-icon="mdi-auto-fix">
            Generar contenido
          </v-btn>
        </template>
        <v-list>
          <v-list-item title="Descripción y datos técnicos" @click="emit('start', 'full')" />
          <v-list-item title="Sólo descripción" @click="emit('start', 'description')" />
          <v-list-item title="Sólo datos técnicos" @click="emit('start', 'technical')" />
        </v-list>
      </v-menu>
    </v-card-title>
    <v-progress-linear v-if="loading || isActive" indeterminate color="primary" />
    <v-card-text>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
      <p v-if="job" class="mb-3">
        Estado: <strong>{{ job.status }}</strong>
        <span v-if="job.stage"> · Etapa: {{ job.stage }}</span>
        <span v-if="job.provider"> · {{ job.provider }} / {{ job.model }}</span>
      </p>
      <v-alert v-if="job?.error" type="error" variant="tonal">{{ job.error.message }}</v-alert>
      <template v-if="proposalFields.length">
        <div class="text-subtitle-2 mb-2">Campos pendientes</div>
        <v-checkbox
          v-for="field in proposalFields"
          :key="field"
          v-model="selected"
          :label="`${label(field)} · confianza ${Math.round((job?.confidence?.[field] ?? 0) * 100)}%`"
          :value="field"
          density="compact"
          hide-details
        />
        <div class="d-flex ga-2 mt-4">
          <v-btn :disabled="!selected.length || loading" color="primary" @click="emit('apply', selected)">Aplicar seleccionados</v-btn>
          <v-btn :disabled="loading" variant="tonal" @click="emit('discard')">Descartar</v-btn>
        </div>
      </template>
      <div v-if="job?.sources.length" class="mt-5">
        <div class="text-subtitle-2">Fuentes consultadas</div>
        <v-list density="compact">
          <v-list-item
            v-for="source in job.sources"
            :key="source.url"
            :href="source.url"
            :subtitle="source.url"
            :title="source.title || source.source_type || 'Fuente web'"
            target="_blank"
          />
        </v-list>
      </div>
      <p v-if="!job" class="text-medium-emphasis mb-0">Todavía no hay actividad de enriquecimiento en esta sesión.</p>
    </v-card-text>
  </v-card>
</template>
