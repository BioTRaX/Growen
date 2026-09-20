<!-- NG-HEADER: Nombre de archivo: MarketPriceBadge.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/market/components/MarketPriceBadge.vue -->
<!-- NG-HEADER: Descripción: Badge accesible de posición del precio contra el promedio. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed } from 'vue'
import { PRICE_PRESENTATION } from '../priceComparison'
import type { PricePosition } from '../types'
const props = defineProps<{ position: PricePosition; delta: number | null; label?: string }>()
const presentation = computed(() => PRICE_PRESENTATION[props.position] ?? PRICE_PRESENTATION.unavailable)
const signed = computed(() => props.delta === null ? '' : `${props.delta > 0 ? '+' : ''}${props.delta.toFixed(2)}%`)
</script>
<template><v-tooltip :text="`${label || presentation.label}${signed ? ` (${signed})` : ''}`"><template #activator="{ props: tooltipProps }"><v-chip v-bind="tooltipProps" :color="presentation.color" :prepend-icon="presentation.icon" size="small" variant="flat"><span>{{ signed || 'Sin comparación' }}</span><span class="d-none d-lg-inline ml-1">· {{ label || presentation.label }}</span></v-chip></template></v-tooltip></template>
