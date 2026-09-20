<!-- NG-HEADER: Nombre de archivo: StockFilters.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/stock/components/StockFilters.vue -->
<!-- NG-HEADER: Descripción: Filtros persistentes del listado Vue de Stock. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import type { ProductCategory, ProductSupplier } from '../../products/types'
import type { StockFilters } from '../types'
defineProps<{ modelValue: StockFilters; categories: ProductCategory[]; suppliers: ProductSupplier[]; loading?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: Partial<StockFilters>] }>()
</script>
<template>
  <v-card class="mb-5" variant="tonal"><v-card-text><v-row dense>
    <v-col cols="12" md="5"><v-text-field clearable hide-details label="Buscar producto o SKU" :model-value="modelValue.q" prepend-inner-icon="mdi-magnify" @update:model-value="emit('update:modelValue', { q: $event ?? '' })" /></v-col>
    <v-col cols="12" md="3"><v-autocomplete clearable hide-details item-title="name" item-value="id" :items="suppliers" label="Proveedor" :loading="loading" :model-value="modelValue.supplier_id" @update:model-value="emit('update:modelValue', { supplier_id: $event ?? null })" /></v-col>
    <v-col cols="12" md="4"><v-select clearable hide-details item-title="path" item-value="id" :items="categories" label="Categoría" :loading="loading" :model-value="modelValue.category_id" @update:model-value="emit('update:modelValue', { category_id: $event ?? null })" /></v-col>
  </v-row></v-card-text></v-card>
</template>
