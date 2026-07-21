<!-- NG-HEADER: Nombre de archivo: ProductsFilters.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductsFilters.vue -->
<!-- NG-HEADER: Descripción: Filtros operativos del catálogo Vue de Productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import type { ProductCategory, ProductListFilters, ProductSupplier } from '../types'

defineProps<{
  modelValue: ProductListFilters
  categories: ProductCategory[]
  suppliers: ProductSupplier[]
  metadataLoading?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: Partial<ProductListFilters>] }>()

function update(value: Partial<ProductListFilters>): void {
  emit('update:modelValue', value)
}
</script>

<template>
  <v-card class="mb-5" variant="tonal">
    <v-card-text>
      <v-row dense>
        <v-col cols="12" lg="4" md="6">
          <v-text-field
            clearable
            hide-details
            label="Buscar por nombre o SKU"
            :model-value="modelValue.q"
            prepend-inner-icon="mdi-magnify"
            @update:model-value="update({ q: $event ?? '' })"
          />
        </v-col>
        <v-col cols="12" lg="2" md="6">
          <v-autocomplete
            clearable
            hide-details
            item-title="name"
            item-value="id"
            :items="suppliers"
            label="Proveedor"
            :loading="metadataLoading"
            :model-value="modelValue.supplier_id"
            @update:model-value="update({ supplier_id: $event ?? null })"
          />
        </v-col>
        <v-col cols="12" lg="2" md="6">
          <v-select
            clearable
            hide-details
            item-title="path"
            item-value="id"
            :items="categories"
            label="Categoría"
            :loading="metadataLoading"
            :model-value="modelValue.category_id"
            @update:model-value="update({ category_id: $event ?? null })"
          />
        </v-col>
        <v-col cols="12" lg="2" md="6">
          <v-select
            hide-details
            :items="[{ title: 'Todo el stock', value: '' }, { title: 'Con stock', value: 'gt:0' }, { title: 'Sin stock', value: 'eq:0' }]"
            label="Stock"
            :model-value="modelValue.stock"
            @update:model-value="update({ stock: $event })"
          />
        </v-col>
        <v-col cols="12" lg="2" md="6">
          <v-select
            hide-details
            :items="[{ title: 'Todas las fechas', value: '' }, { title: 'Últimas 24 h', value: 1 }, { title: 'Últimos 7 días', value: 7 }, { title: 'Últimos 30 días', value: 30 }]"
            label="Recientes"
            :model-value="modelValue.recent"
            @update:model-value="update({ recent: $event })"
          />
        </v-col>
      </v-row>
      <v-btn-toggle
        class="mt-4"
        color="primary"
        density="comfortable"
        divided
        mandatory
        :model-value="modelValue.type"
        variant="outlined"
        @update:model-value="update({ type: $event })"
      >
        <v-btn value="all">Todos</v-btn>
        <v-btn value="canonical">Canónicos</v-btn>
        <v-btn value="supplier">Sin canónico</v-btn>
      </v-btn-toggle>
    </v-card-text>
  </v-card>
</template>
