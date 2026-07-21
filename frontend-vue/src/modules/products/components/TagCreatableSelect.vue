<!-- NG-HEADER: Nombre de archivo: TagCreatableSelect.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/TagCreatableSelect.vue -->
<!-- NG-HEADER: Descripción: Selector múltiple, buscable y creable de tags de producto. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { createProductTag, listProductTags } from '../api/products'
import type { ProductTag } from '../types'

interface TagOption extends ProductTag {
  title: string
  create?: boolean
}

const props = withDefaults(defineProps<{
  modelValue: string[]
  label?: string
  disabled?: boolean
}>(), {
  label: 'Tags (opcional)',
  disabled: false,
})
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const search = ref('')
const tags = ref<ProductTag[]>([])
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined

function clean(value: string): string {
  return value.trim().replace(/\s+/g, ' ')
}

function dedupe(values: string[]): string[] {
  const result = new Map<string, string>()
  values.map(clean).filter(Boolean).forEach((value) => result.set(value.toLocaleLowerCase('es'), value))
  return [...result.values()]
}

const options = computed<TagOption[]>(() => {
  const current: TagOption[] = tags.value.map((tag) => ({ ...tag, title: tag.name }))
  const name = clean(search.value)
  if (name && !tags.value.some((tag) => tag.name.toLocaleLowerCase('es') === name.toLocaleLowerCase('es')) &&
    !props.modelValue.some((tag) => tag.toLocaleLowerCase('es') === name.toLocaleLowerCase('es'))) {
    current.push({ id: -1, name, title: `Agregar “${name}”`, create: true })
  }
  return current
})

async function loadTags(query = ''): Promise<void> {
  controller?.abort()
  const request = new AbortController()
  controller = request
  loading.value = true
  try {
    tags.value = await listProductTags(query, request.signal)
  } catch (cause) {
    if (request.signal.aborted) return
    error.value = getHttpErrorMessage(cause, 'No se pudieron buscar los tags')
  } finally {
    if (controller === request) loading.value = false
  }
}

async function updateSelection(values: string[]): Promise<void> {
  const selected = dedupe(values)
  const prior = new Set(props.modelValue.map((name) => name.toLocaleLowerCase('es')))
  const pending = selected.find((name) => !prior.has(name.toLocaleLowerCase('es')) &&
    !tags.value.some((tag) => tag.name.toLocaleLowerCase('es') === name.toLocaleLowerCase('es')))
  if (!pending) {
    emit('update:modelValue', selected)
    return
  }
  loading.value = true
  error.value = ''
  try {
    const created = await createProductTag(pending)
    if (!tags.value.some((tag) => tag.id === created.id)) tags.value.push(created)
    emit('update:modelValue', dedupe(selected.map((name) => name === pending ? created.name : name)))
    search.value = ''
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo crear el tag')
  } finally {
    loading.value = false
  }
}

watch(search, (value) => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => void loadTags(value), 250)
})
void loadTags()
onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
  controller?.abort()
})
</script>

<template>
  <div>
    <v-autocomplete
      v-model:search="search"
      chips
      closable-chips
      :disabled="disabled"
      :items="options"
      item-title="title"
      item-value="name"
      :label="label"
      :loading="loading"
      :model-value="modelValue"
      multiple
      @update:model-value="updateSelection"
    >
      <template #item="{ props: itemProps, item }">
        <v-list-item
          v-bind="itemProps"
          :prepend-icon="item.raw.create ? 'mdi-plus-circle-outline' : 'mdi-tag-outline'"
          :subtitle="item.raw.create ? 'Crear y seleccionar' : undefined"
        />
      </template>
      <template #no-data><v-list-item title="Escribí para buscar o agregar un tag" /></template>
    </v-autocomplete>
    <div v-if="error" class="text-error text-caption mt-1">{{ error }}</div>
  </div>
</template>
