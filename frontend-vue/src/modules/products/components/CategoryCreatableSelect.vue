<!-- NG-HEADER: Nombre de archivo: CategoryCreatableSelect.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CategoryCreatableSelect.vue -->
<!-- NG-HEADER: Descripción: Selector escribible para categorías planas con alta inline. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { createProductCategory } from '../api/products'
import type { ProductCategory } from '../types'

interface CategoryOption extends ProductCategory {
  displayTitle: string
  create?: boolean
}

const props = withDefaults(defineProps<{
  modelValue: number | null
  categories: ProductCategory[]
  label: string
  kind?: ProductCategory['kind']
  parentId?: number | null
  disabled?: boolean
  clearable?: boolean
  showPath?: boolean
}>(), {
  kind: undefined,
  parentId: undefined,
  disabled: false,
  clearable: false,
  showPath: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
  created: [category: ProductCategory]
}>()

const search = ref('')
const creating = ref(false)
const error = ref('')
const effectiveKind = computed<ProductCategory['kind']>(() => props.kind ?? (props.parentId === null ? 'category' : 'subcategory'))

function normalize(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLocaleLowerCase('es')
}

const normalizedSearch = computed(() => normalize(search.value))
const canCreate = computed(() => Boolean(
  normalizedSearch.value &&
  !props.categories.some((category) => category.kind === effectiveKind.value && normalize(category.name) === normalizedSearch.value),
))
const options = computed<CategoryOption[]>(() => {
  const current: CategoryOption[] = props.categories
    .filter((category) => category.kind === effectiveKind.value)
    .map((category) => ({ ...category, displayTitle: props.showPath ? category.path : category.name }))
  if (canCreate.value) {
    const name = search.value.trim().replace(/\s+/g, ' ')
    current.push({
      id: -1,
      name,
      parent_id: null,
      kind: effectiveKind.value,
      path: name,
      displayTitle: `Agregar “${name}”`,
      create: true,
    })
  }
  return current
})

async function selectOption(value: number | null): Promise<void> {
  if (value === null) {
    emit('update:modelValue', null)
    return
  }
  const option = options.value.find((item) => item.id === value)
  if (!option) return
  if (!option.create) {
    error.value = ''
    emit('update:modelValue', value)
    return
  }
  await createInline(option.name)
}

async function createInline(name: string): Promise<void> {
  if (creating.value || !name.trim()) return
  creating.value = true
  error.value = ''
  try {
    const category = await createProductCategory(name, effectiveKind.value)
    emit('created', category)
    emit('update:modelValue', category.id)
    search.value = category.name
  } catch (cause) {
    const fallback = effectiveKind.value === 'category' ? 'la categoría' : 'la subcategoría'
    error.value = getHttpErrorMessage(cause, `No se pudo crear ${fallback}`)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div>
    <v-autocomplete
      v-model:search="search"
      :clearable="clearable"
      :disabled="disabled"
      :items="options"
      item-title="displayTitle"
      item-value="id"
      :loading="creating"
      :model-value="modelValue"
      :label="label"
      @update:model-value="selectOption"
    >
      <template #item="{ props: itemProps, item }">
        <v-list-item
          v-bind="itemProps"
          :prepend-icon="item.raw.create ? 'mdi-plus-circle-outline' : undefined"
          :subtitle="item.raw.create ? 'Crear y seleccionar' : undefined"
        />
      </template>
      <template #no-data><v-list-item title="No se encontraron resultados" /></template>
    </v-autocomplete>
    <div v-if="error" class="text-error text-caption mt-1">{{ error }}</div>
  </div>
</template>
