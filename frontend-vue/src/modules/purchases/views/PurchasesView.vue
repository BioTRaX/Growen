<!-- NG-HEADER: Nombre de archivo: PurchasesView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/views/PurchasesView.vue -->
<!-- NG-HEADER: Descripción: Listado e importación de remitos Santa Planta. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SupplierSelect from '../../suppliers/components/SupplierSelect.vue'
import { getHttpErrorMessage } from '../../../services/http'
import { importSantaPlanta, listPurchases, type Purchase } from '../../../services/purchases'

const router = useRouter()
const rows = ref<Purchase[]>([])
const loading = ref(false)
const error = ref('')
const supplierId = ref<number | null>(null)
const file = ref<File | File[] | null>(null)

function selectedFile(): File | null {
  return Array.isArray(file.value) ? (file.value[0] ?? null) : file.value
}

async function refresh() {
  loading.value = true
  try { rows.value = (await listPurchases()).items } finally { loading.value = false }
}

async function upload() {
  const document = selectedFile()
  if (!supplierId.value || !document) return
  error.value = ''
  loading.value = true
  try {
    const result = await importSantaPlanta(supplierId.value, document)
    await router.push(`/compras/${result.purchase_id}`)
  } catch (exception) {
    error.value = getHttpErrorMessage(exception, 'No se pudo importar el remito')
  } finally { loading.value = false }
}

onMounted(refresh)
</script>

<template>
  <v-container fluid class="py-8">
    <div class="d-flex align-center justify-space-between mb-6">
      <div><h1 class="text-h4">Compras</h1><p class="text-medium-emphasis">Remitos e ingesta transaccional de productos</p></div>
      <v-btn color="primary" prepend-icon="mdi-plus" to="/compras/nueva">Carga manual</v-btn>
    </div>
    <v-alert v-if="error" class="mb-4" type="error">{{ error }}</v-alert>
    <v-card class="mb-6">
      <v-card-title>Importar remito Santa Planta</v-card-title>
      <v-card-text class="d-flex ga-4 flex-wrap align-start">
        <SupplierSelect v-model="supplierId" label="Proveedor" />
        <v-file-input v-model="file" accept="application/pdf,image/jpeg,image/png" label="PDF, JPG o PNG" hide-details />
        <v-btn class="mt-1" :disabled="!supplierId || !selectedFile()" :loading="loading" color="primary" @click="upload">Procesar</v-btn>
      </v-card-text>
      <v-card-subtitle class="pb-4">La extracción automática disponible en esta etapa usa el perfil Santa Planta.</v-card-subtitle>
    </v-card>
    <v-data-table :headers="[
      { title: 'Proveedor', key: 'supplier_name' }, { title: 'Remito', key: 'remito_number' },
      { title: 'Fecha', key: 'remito_date' }, { title: 'Estado', key: 'status' },
      { title: 'Total', key: 'documented_total' }, { title: '', key: 'actions', sortable: false },
    ]" :items="rows" :loading="loading">
      <template #item.status="{ value }"><v-chip :color="value === 'CONFIRMADA' ? 'success' : 'warning'" size="small">{{ value }}</v-chip></template>
      <template #item.documented_total="{ item }">{{ item.documented_total == null ? '-' : `$ ${item.documented_total.toLocaleString('es-AR')}` }}</template>
      <template #item.actions="{ item }"><v-btn size="small" variant="text" :to="`/compras/${item.id}`">Abrir</v-btn></template>
    </v-data-table>
  </v-container>
</template>
