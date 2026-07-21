<!-- NG-HEADER: Nombre de archivo: SupplierSelect.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/suppliers/components/SupplierSelect.vue -->
<!-- NG-HEADER: Descripción: Selector buscable y reutilizable de proveedores. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { searchSuppliers, type SupplierSummary } from '../../../services/suppliers'
import SupplierCreateDialog from './SupplierCreateDialog.vue'

defineProps<{ modelValue: number | null; label?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const auth = useAuthStore()
const items = ref<SupplierSummary[]>([])
const query = ref('')
const loading = ref(false)
const error = ref('')
const createOpen = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function load(value = '') {
  loading.value = true
  error.value = ''
  try { items.value = await searchSuppliers(value) }
  catch (cause) { error.value = getHttpErrorMessage(cause, 'No se pudieron cargar los proveedores') }
  finally { loading.value = false }
}

watch(query, (value) => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => load(value), 250)
})

function created(supplier: SupplierSummary) {
  if (!items.value.some((item) => item.id === supplier.id)) items.value.unshift(supplier)
  emit('update:modelValue', supplier.id)
}

onMounted(() => load())
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <div class="d-flex align-start ga-2 flex-grow-1">
    <v-autocomplete
      :model-value="modelValue" v-model:search="query" :items="items" item-title="name" item-value="id"
      :label="label ?? 'Proveedor'" :loading="loading" :error-messages="error || undefined" clearable
      no-data-text="No hay proveedores" @update:model-value="emit('update:modelValue', $event)"
    >
      <template #item="{ props: itemProps, item }">
        <v-list-item v-bind="itemProps" :subtitle="item.raw.slug" />
      </template>
    </v-autocomplete>
    <v-btn v-if="auth.role === 'admin'" class="mt-1" icon="mdi-plus" variant="tonal" title="Crear proveedor" @click="createOpen = true" />
    <SupplierCreateDialog v-model="createOpen" @created="created" />
  </div>
</template>
