<!-- NG-HEADER: Nombre de archivo: MassCanonicalResults.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/MassCanonicalResults.vue -->
<!-- NG-HEADER: Descripción: Progreso y resultados por fila del alta masiva canónica. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import type { CanonicalBatchJobResponse, MassCanonicalDraftRow } from '../types'

defineProps<{ job: CanonicalBatchJobResponse | null; rows: MassCanonicalDraftRow[] }>()
</script>

<template>
  <div>
    <v-progress-linear
      class="mb-4"
      color="primary"
      :indeterminate="!job"
      :model-value="job ? (job.processed_items / Math.max(job.total_items, 1)) * 100 : 0"
    />
    <div v-if="job" class="d-flex flex-wrap ga-2 mb-4">
      <v-chip color="primary" variant="tonal">{{ job.processed_items }}/{{ job.total_items }} procesados</v-chip>
      <v-chip color="success" variant="tonal">{{ job.success_count }} creados</v-chip>
      <v-chip color="error" variant="tonal">{{ job.error_count }} con error</v-chip>
    </div>
    <v-table v-if="job" density="compact">
      <thead><tr><th>Producto</th><th>Estado</th><th>SKU definitivo / error</th></tr></thead>
      <tbody>
        <tr v-for="item in job.items" :key="item.position">
          <td>{{ rows[item.position]?.name || `Fila ${item.position + 1}` }}</td>
          <td><v-chip :color="item.status === 'SUCCEEDED' ? 'success' : item.status === 'FAILED' ? 'error' : 'info'" size="small">{{ item.status }}</v-chip></td>
          <td><code v-if="item.sku_custom">{{ item.sku_custom }}</code><span v-else>{{ item.error?.message || 'Procesando…' }}</span></td>
        </tr>
      </tbody>
    </v-table>
  </div>
</template>
