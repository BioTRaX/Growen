<!-- NG-HEADER: Nombre de archivo: ProductsTable.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductsTable.vue -->
<!-- NG-HEADER: Descripción: Tabla responsive de consulta del catálogo Vue de Productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import type { ProductListItem } from '../types'
import { effectiveSalePrice } from '../productPresentation'

defineProps<{ items: ProductListItem[]; loading: boolean; canEdit: boolean; selected: number[] }>()
const emit = defineEmits<{
  'update:selected': [value: number[]]
  editStock: [product: ProductListItem]
  editPrice: [product: ProductListItem]
  delete: [product: ProductListItem]
}>()

const headers = [
  { title: 'Producto', key: 'preferred_name', minWidth: 260 },
  { title: 'SKU', key: 'sku', minWidth: 130 },
  { title: 'Proveedor', key: 'supplier.name', minWidth: 160 },
  { title: 'Precio efectivo', key: 'effective_price', align: 'end' as const },
  { title: 'Stock', key: 'stock', align: 'end' as const },
  { title: 'Categoría', key: 'category_path', minWidth: 180 },
  { title: 'Canónico', key: 'canonical_product_id', align: 'center' as const },
  { title: '', key: 'actions', sortable: false, align: 'end' as const },
]

function formatPrice(value: number | null): string {
  return value === null ? '—' : new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}
</script>

<template>
  <v-data-table
    class="products-table"
    :headers="headers"
    hide-default-footer
    :items="items"
    item-value="product_id"
    :items-per-page="-1"
    :loading="loading"
    :model-value="selected"
    :show-select="canEdit"
    @update:model-value="emit('update:selected', $event)"
  >
    <template #item.preferred_name="{ item }">
      <div class="py-2">
        <router-link class="font-weight-medium text-decoration-none" :to="`/productos/${item.product_id}`">
          {{ item.preferred_name || item.canonical_name || item.name }}
        </router-link>
        <div v-if="item.tags.length" class="d-flex flex-wrap ga-1 mt-1">
          <v-chip v-for="tag in item.tags" :key="tag.id" size="x-small" variant="tonal">{{ tag.name }}</v-chip>
        </div>
      </div>
    </template>
    <template #item.sku="{ item }">{{ item.canonical_sku || item.first_variant_sku || '—' }}</template>
    <template #item.effective_price="{ item }">
      <div class="d-flex align-center justify-end ga-1">
        <span>{{ formatPrice(effectiveSalePrice(item)) }}</span>
        <v-btn v-if="canEdit" icon="mdi-pencil" size="x-small" title="Editar precio" variant="text" @click="emit('editPrice', item)" />
      </div>
    </template>
    <template #item.stock="{ item }">
      <div class="d-flex align-center justify-end ga-1">
        <span>{{ item.stock }}</span>
        <v-btn v-if="canEdit" icon="mdi-pencil" size="x-small" title="Editar stock" variant="text" @click="emit('editStock', item)" />
      </div>
    </template>
    <template #item.category_path="{ value }">{{ value || '—' }}</template>
    <template #item.canonical_product_id="{ value }">
      <v-chip :color="value ? 'success' : 'warning'" size="small" variant="tonal">
        {{ value ? 'Asignado' : 'Pendiente' }}
      </v-chip>
    </template>
    <template #item.actions="{ item }">
      <div class="d-flex justify-end">
        <v-btn :to="`/productos/${item.product_id}`" size="small" variant="text">Ver detalle</v-btn>
        <v-btn v-if="canEdit" color="error" icon="mdi-delete-outline" size="small" title="Borrar producto" variant="text" @click="emit('delete', item)" />
      </div>
    </template>
    <template #no-data>
      <div class="pa-8 text-center text-medium-emphasis">No hay productos para los filtros seleccionados.</div>
    </template>
  </v-data-table>
</template>

<style scoped>
.products-table {
  overflow-x: auto;
}
</style>
