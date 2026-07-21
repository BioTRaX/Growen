<!-- NG-HEADER: Nombre de archivo: SuppliersView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/suppliers/views/SuppliersView.vue -->
<!-- NG-HEADER: Descripción: Listado y alta básica de proveedores en Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { listSuppliers, type SupplierSummary } from '../../../services/suppliers'
import SupplierCreateDialog from '../components/SupplierCreateDialog.vue'

const auth = useAuthStore()
const rows = ref<SupplierSummary[]>([])
const query = ref('')
const loading = ref(false)
const error = ref('')
const createOpen = ref(false)
const filtered = computed(() => {
  const value = query.value.trim().toLowerCase()
  return value ? rows.value.filter((item) => item.name.toLowerCase().includes(value) || item.slug.toLowerCase().includes(value)) : rows.value
})

async function refresh() {
  loading.value = true; error.value = ''
  try { rows.value = await listSuppliers() }
  catch (cause) { error.value = getHttpErrorMessage(cause, 'No se pudieron cargar los proveedores') }
  finally { loading.value = false }
}

function created(supplier: SupplierSummary) {
  rows.value = [supplier, ...rows.value.filter((item) => item.id !== supplier.id)]
}

onMounted(refresh)
</script>

<template>
  <v-container fluid class="py-8">
    <div class="d-flex align-center justify-space-between mb-6">
      <div><h1 class="text-h4">Proveedores</h1><p class="text-medium-emphasis">Directorio utilizado por Compras</p></div>
      <v-btn v-if="auth.role === 'admin'" color="primary" prepend-icon="mdi-plus" @click="createOpen = true">Nuevo proveedor</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
    <v-card>
      <v-card-text><v-text-field v-model="query" prepend-inner-icon="mdi-magnify" label="Buscar por nombre o identificador" clearable hide-details /></v-card-text>
      <v-data-table :items="filtered" :loading="loading" :headers="[
        { title: 'Nombre', key: 'name' }, { title: 'Identificador', key: 'slug' },
        { title: 'Archivos', key: 'files_count' }, { title: 'Última carga', key: 'last_upload_at' },
      ]" />
    </v-card>
    <SupplierCreateDialog v-model="createOpen" @created="created" />
  </v-container>
</template>
