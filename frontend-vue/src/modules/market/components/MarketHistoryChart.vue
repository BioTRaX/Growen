<!-- NG-HEADER: Nombre de archivo: MarketHistoryChart.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/market/components/MarketHistoryChart.vue -->
<!-- NG-HEADER: Descripción: Gráfico SVG liviano del promedio histórico de Mercado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed } from 'vue'
import type { HistoryPoint } from '../types'
const props = defineProps<{ items: HistoryPoint[] }>()
const references = computed(() => props.items.filter(item => item.observation_type === 'reference'))
const polyline = computed(() => { const rows = references.value; if (rows.length < 2) return ''; const prices = rows.map(row => row.price); const min = Math.min(...prices); const max = Math.max(...prices); const span = max - min || 1; return rows.map((row, index) => `${10 + index * 580 / (rows.length - 1)},${110 - (row.price - min) * 90 / span}`).join(' ') })
</script>
<template><div><svg v-if="references.length > 1" viewBox="0 0 600 130" role="img" aria-label="Evolución del promedio de Mercado"><polyline :points="polyline" fill="none" stroke="currentColor" stroke-width="4" /><line x1="10" y1="115" x2="590" y2="115" stroke="currentColor" opacity=".25" /></svg><v-empty-state v-else density="compact" title="Sin histórico suficiente" text="Se necesitan al menos dos promedios." icon="mdi-chart-line" /></div></template>
