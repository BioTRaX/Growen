<!-- NG-HEADER: Nombre de archivo: CustomersView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/customers/views/CustomersView.vue -->
<!-- NG-HEADER: Descripción: Listado, filtros y mantenimiento de clientes. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createCustomer, deactivateCustomer, listCustomers, reactivateCustomer, type Customer } from '../../../services/customers'
import { getHttpErrorMessage } from '../../../services/http'

const router = useRouter()
const rows = ref<Customer[]>([]); const total = ref(0); const page = ref(1); const pages = ref(1)
const q = ref(''); const kind = ref<string | null>(null); const active = ref(true); const loading = ref(false); const error = ref('')
const dialog = ref(false); const form = ref<Partial<Customer>>({ name: '', kind: 'minorista' })
let timer: ReturnType<typeof setTimeout> | undefined; let controller: AbortController | undefined

async function refresh() {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { const data = await listCustomers({ q: q.value || undefined, kind: kind.value || undefined, only_active: active.value, page: page.value, page_size: 25 }, controller.signal); rows.value = data.items; total.value = data.total; pages.value = data.pages }
  catch (exception) { const message = getHttpErrorMessage(exception); if (message) error.value = message }
  finally { loading.value = false }
}
watch([q, kind, active], () => { page.value = 1; clearTimeout(timer); timer = setTimeout(refresh, 300) })
watch(page, refresh); onMounted(refresh)
async function save() { try { await createCustomer(form.value); dialog.value = false; form.value = { name: '', kind: 'minorista' }; await refresh() } catch (e) { error.value = getHttpErrorMessage(e) } }
async function toggle(row: Customer) { row.is_active ? await deactivateCustomer(row.id) : await reactivateCustomer(row.id); await refresh() }
</script>

<template><v-container fluid class="py-8">
  <div class="d-flex justify-space-between align-center mb-6"><div><h1 class="text-h4">Clientes</h1><p class="text-medium-emphasis">CRM, actividad y cuenta corriente</p></div><v-btn color="primary" prepend-icon="mdi-account-plus" @click="dialog=true">Nuevo cliente</v-btn></div>
  <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{ error }}</v-alert>
  <v-card><v-card-text class="d-flex ga-3 flex-wrap"><v-text-field v-model="q" label="Buscar" prepend-inner-icon="mdi-magnify" hide-details clearable /><v-select v-model="kind" :items="['cf','ri','minorista','mayorista']" label="Tipo" hide-details clearable /><v-switch v-model="active" label="Solo activos" hide-details /></v-card-text>
  <v-data-table :headers="[{title:'Nombre',key:'name'},{title:'Documento',key:'document_number'},{title:'Contacto',key:'email'},{title:'Tipo',key:'kind'},{title:'Estado',key:'is_active'},{title:'',key:'actions',sortable:false}]" :items="rows" :loading="loading" hide-default-footer>
    <template #item.is_active="{ item }"><v-chip :color="item.is_active?'success':'grey'" size="small">{{ item.is_active?'Activo':'Inactivo' }}</v-chip></template>
    <template #item.actions="{ item }"><v-btn variant="text" size="small" @click="router.push(`/clientes/${item.id}`)">Abrir</v-btn><v-btn variant="text" size="small" @click="toggle(item)">{{ item.is_active?'Desactivar':'Reactivar' }}</v-btn></template>
  </v-data-table><v-card-actions class="justify-center"><v-pagination v-model="page" :length="Math.max(1,pages)" /></v-card-actions></v-card>
  <v-dialog v-model="dialog" max-width="680"><v-card><v-card-title>Nuevo cliente</v-card-title><v-card-text><v-row><v-col cols="12"><v-text-field v-model="form.name" label="Nombre *" /></v-col><v-col cols="6"><v-text-field v-model="form.email" label="Email" /></v-col><v-col cols="6"><v-text-field v-model="form.phone" label="Teléfono" /></v-col><v-col cols="4"><v-select v-model="form.document_type" :items="['DNI','CUIT']" label="Documento" /></v-col><v-col cols="8"><v-text-field v-model="form.document_number" label="Número" /></v-col><v-col cols="6"><v-select v-model="form.kind" :items="['cf','ri','minorista','mayorista']" label="Tipo" /></v-col><v-col cols="6"><v-text-field v-model.number="form.credit_limit" type="number" label="Límite de crédito" /></v-col></v-row></v-card-text><v-card-actions><v-spacer/><v-btn @click="dialog=false">Cancelar</v-btn><v-btn color="primary" :disabled="!form.name?.trim()" @click="save">Crear</v-btn></v-card-actions></v-card></v-dialog>
</v-container></template>
