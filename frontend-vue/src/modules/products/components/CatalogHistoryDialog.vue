<!-- NG-HEADER: Nombre de archivo: CatalogHistoryDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CatalogHistoryDialog.vue -->
<!-- NG-HEADER: Descripción: Histórico Vue de catálogos generados desde Productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { apiUrl, downloadBlob } from '../../../services/transports'
import { deleteCatalog, listCatalogs, type CatalogListItem } from '../../../services/catalogs'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const auth = useAuthStore()
const items = ref<CatalogListItem[]>([])
const page = ref(1)
const pages = ref(1)
const total = ref(0)
const fromDate = ref('')
const toDate = ref('')
const loading = ref(false)
const error = ref('')
let controller: AbortController | undefined

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const result = await listCatalogs({ page: page.value, page_size: 20, from_dt: fromDate.value || undefined, to_dt: toDate.value || undefined }, controller.signal)
    items.value = result.items
    total.value = result.total
    pages.value = Math.max(1, result.pages)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo cargar el histórico de catálogos')
  } finally { loading.value = false }
}

async function remove(item: CatalogListItem): Promise<void> {
  if (!confirm(`¿Eliminar el catálogo ${item.id}?`)) return
  try { await deleteCatalog(item.id); await load() } catch (cause) { error.value = getHttpErrorMessage(cause, 'No se pudo eliminar el catálogo') }
}

watch(() => props.modelValue, (open) => { if (open) void load(); else controller?.abort() })
watch([page, fromDate, toDate], () => { if (props.modelValue) void load() })
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="900" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Histórico de catálogos</v-card-title>
      <v-card-text>
        <v-row dense class="mb-3">
          <v-col cols="12" sm="5"><v-text-field v-model="fromDate" hide-details label="Desde" type="date" /></v-col>
          <v-col cols="12" sm="5"><v-text-field v-model="toDate" hide-details label="Hasta" type="date" /></v-col>
          <v-col cols="12" sm="2"><v-btn block variant="text" @click="fromDate = ''; toDate = ''; page = 1">Limpiar</v-btn></v-col>
        </v-row>
        <v-alert v-if="error" class="mb-3" type="error" variant="tonal">{{ error }}</v-alert>
        <v-data-table :headers="[{ title: 'Catálogo', key: 'id' }, { title: 'Fecha', key: 'modified_at' }, { title: 'Tamaño', key: 'size' }, { title: '', key: 'actions', sortable: false }]" :items="items" :items-per-page="-1" :loading="loading">
          <template #item.id="{ item }"><span>{{ item.id }}</span><v-chip v-if="item.latest" class="ml-2" size="x-small">actual</v-chip></template>
          <template #item.modified_at="{ value }">{{ new Date(value).toLocaleString('es-AR') }}</template>
          <template #item.size="{ value }">{{ (Number(value) / 1024).toFixed(1) }} KB</template>
          <template #item.actions="{ item }">
            <v-btn :href="apiUrl(`/catalogs/${item.id}`)" target="_blank" size="small" variant="text">Ver</v-btn>
            <v-btn size="small" variant="text" @click="downloadBlob(`/catalogs/${item.id}/download`, item.filename)">Descargar</v-btn>
            <v-btn v-if="auth.role === 'admin'" color="error" size="small" variant="text" @click="remove(item)">Borrar</v-btn>
          </template>
        </v-data-table>
        <div class="d-flex align-center justify-space-between mt-3"><span>{{ total }} resultado(s)</span><v-pagination v-model="page" :length="pages" /></div>
      </v-card-text>
      <v-card-actions class="justify-end"><v-btn @click="emit('update:modelValue', false)">Cerrar</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>
