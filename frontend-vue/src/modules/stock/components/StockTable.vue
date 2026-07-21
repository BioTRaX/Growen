<!-- NG-HEADER: Nombre de archivo: StockTable.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/stock/components/StockTable.vue -->
<!-- NG-HEADER: Descripción: Tabla responsive de existencias y precios. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import type { ProductListItem } from '../../products/types'
import { effectiveSalePrice } from '../../products/productPresentation'
defineProps<{ items: ProductListItem[]; loading: boolean; canEdit: boolean }>()
const emit = defineEmits<{ editStock: [item: ProductListItem]; editSale: [item: ProductListItem]; editBuy: [item: ProductListItem] }>()
const headers = [
  { title: 'Producto', key: 'preferred_name' }, { title: 'Proveedor', key: 'supplier' },
  { title: 'Precio venta', key: 'sale', align: 'end' as const }, { title: 'Compra', key: 'buy', align: 'end' as const },
  { title: 'Stock', key: 'stock', align: 'end' as const }, { title: 'Categoría', key: 'category_path' },
  { title: 'Actualizado', key: 'updated_at' },
]
function money(value: number | null): string { return value === null ? '—' : `$ ${Number(value).toFixed(2)}` }
function qty(value: number): string { return Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 }) }
</script>
<template><v-data-table :headers="headers" :items="items" :items-per-page="-1" :loading="loading">
  <template #item.preferred_name="{ item }"><v-btn :to="`/productos/${item.product_id}`" variant="text">{{ item.preferred_name || item.name }}</v-btn></template>
  <template #item.supplier="{ item }">{{ item.supplier.name }}</template>
  <template #item.sale="{ item }"><div class="d-flex justify-end align-center"><span>{{ money(effectiveSalePrice(item)) }}</span><v-btn v-if="canEdit" icon="mdi-pencil" size="x-small" variant="text" @click="emit('editSale', item)" /></div></template>
  <template #item.buy="{ item }"><div class="d-flex justify-end align-center"><span>{{ money(item.precio_compra) }}</span><v-btn v-if="canEdit && item.supplier_item_id" icon="mdi-pencil" size="x-small" variant="text" @click="emit('editBuy', item)" /></div></template>
  <template #item.stock="{ item }"><div class="d-flex justify-end align-center"><strong>{{ qty(item.stock) }}</strong><v-btn v-if="canEdit" icon="mdi-pencil" size="x-small" variant="text" @click="emit('editStock', item)" /></div></template>
  <template #item.category_path="{ value }">{{ value || '—' }}</template>
  <template #item.updated_at="{ value }">{{ value ? new Date(value).toLocaleString('es-AR') : '—' }}</template>
  <template #no-data><div class="pa-8 text-center">No hay productos para los filtros seleccionados.</div></template>
</v-data-table></template>
