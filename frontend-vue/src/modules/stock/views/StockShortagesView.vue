<!-- NG-HEADER: Nombre de archivo: StockShortagesView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/stock/views/StockShortagesView.vue -->
<!-- NG-HEADER: Descripción: Vista Vue de listado, métricas y alta de faltantes. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref } from 'vue'

import ShortageReportDialog from '../components/ShortageReportDialog.vue'
import { useShortages } from '../composables/useShortages'
import { SHORTAGE_REASON_LABELS, type ShortageReason } from '../types'

const dialogOpen = ref(false)
const notice = ref('')
const { items, stats, total, pages, loading, statsLoading, error, filters, setFilters, refresh, retry } = useShortages()
const reasonItems = [{ value: undefined, title: 'Todos los motivos' }, ...Object.entries(SHORTAGE_REASON_LABELS).map(([value, title]) => ({ value, title }))]
function quantity(value: number): string { return Number(value).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function date(value: string): string { return new Date(value).toLocaleString('es-AR') }
async function created(message: string): Promise<void> { notice.value = message; await setFilters({ page: 1 }); await refresh() }
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-5">
      <div><h1 class="text-h4">Faltantes de stock</h1><p class="text-medium-emphasis">Registro de descuentos manuales y su trazabilidad.</p></div>
      <div class="d-flex ga-2"><v-btn to="/stock" prepend-icon="mdi-arrow-left">Volver a Stock</v-btn><v-btn color="primary" prepend-icon="mdi-alert-minus" @click="dialogOpen = true">Reportar faltante</v-btn></div>
    </div>
    <v-row class="mb-4">
      <v-col cols="12" md="3"><v-card :loading="statsLoading"><v-card-text><div class="text-h4">{{ stats?.total_items ?? 0 }}</div><div class="text-medium-emphasis">Reportes</div></v-card-text></v-card></v-col>
      <v-col cols="12" md="3"><v-card :loading="statsLoading"><v-card-text><div class="text-h4">{{ quantity(stats?.total_quantity ?? 0) }}</div><div class="text-medium-emphasis">Cantidad faltante</div></v-card-text></v-card></v-col>
      <v-col cols="12" md="3"><v-card :loading="statsLoading"><v-card-text><div class="text-h4">{{ stats?.this_month ?? 0 }}</div><div class="text-medium-emphasis">Este mes</div></v-card-text></v-card></v-col>
      <v-col cols="12" md="3"><v-card :loading="statsLoading"><v-card-text><div class="d-flex flex-wrap ga-1"><v-chip v-for="(count, reason) in stats?.by_reason" :key="reason" size="small">{{ SHORTAGE_REASON_LABELS[reason as ShortageReason] ?? reason }}: {{ count }}</v-chip></div><div class="text-medium-emphasis mt-2">Por motivo</div></v-card-text></v-card></v-col>
    </v-row>
    <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}<template #append><v-btn variant="text" @click="retry">Reintentar</v-btn></template></v-alert>
    <v-card>
      <v-card-text class="d-flex flex-wrap align-center ga-3"><v-select hide-details item-title="title" item-value="value" :items="reasonItems" label="Motivo" :model-value="filters.reason" style="max-width:280px" @update:model-value="setFilters({ reason: $event })" /><span class="text-medium-emphasis">{{ total }} resultado(s)</span></v-card-text>
      <v-data-table :headers="[{ title: 'Fecha', key: 'created_at' }, { title: 'Producto', key: 'product_title' }, { title: 'Cantidad', key: 'quantity', align: 'end' }, { title: 'Motivo', key: 'reason' }, { title: 'Estado', key: 'status' }, { title: 'Usuario', key: 'user_name' }, { title: 'Observación', key: 'observation' }]" :items="items" :items-per-page="-1" :loading="loading">
        <template #item.created_at="{ value }">{{ date(value) }}</template>
        <template #item.product_title="{ item }"><v-btn :to="`/productos/${item.product_id}`" variant="text">{{ item.product_title }}</v-btn></template>
        <template #item.quantity="{ value }"><strong class="text-error">-{{ quantity(value) }}</strong></template>
        <template #item.reason="{ value }"><v-chip size="small">{{ SHORTAGE_REASON_LABELS[value as ShortageReason] ?? value }}</v-chip></template>
        <template #item.status="{ value }"><v-chip :color="value === 'OPEN' ? 'warning' : 'success'" size="small">{{ value === 'OPEN' ? 'Abierto' : 'Conciliado' }}</v-chip></template>
        <template #item.user_name="{ value }">{{ value || '—' }}</template><template #item.observation="{ value }">{{ value || '—' }}</template>
        <template #no-data><div class="pa-8 text-center">No hay faltantes registrados.</div></template>
      </v-data-table>
      <v-divider /><div class="pa-4"><v-pagination :length="pages" :model-value="filters.page" @update:model-value="setFilters({ page: $event })" /></div>
    </v-card>
    <ShortageReportDialog v-model="dialogOpen" @created="created" />
    <v-snackbar :model-value="Boolean(notice)" color="success" @update:model-value="!$event && (notice = '')">{{ notice }}</v-snackbar>
  </v-container>
</template>
