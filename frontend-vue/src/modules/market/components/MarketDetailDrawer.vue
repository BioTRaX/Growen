<!-- NG-HEADER: Nombre de archivo: MarketDetailDrawer.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/market/components/MarketDetailDrawer.vue -->
<!-- NG-HEADER: Descripción: Detalle, fuentes, detección, validación e histórico de Mercado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import {
  addMarketSource, createManualObservation, deleteMarketSource, forceDetectMarketSourcePrice,
  getMarketHistory, getMarketJob, getProductSources, manuallyValidateMarketSource, refreshProduct,
  restoreMarketSource, revalidateMarketSource, updateMarketSource,
} from '../api/market'
import type { HistoryPoint, MarketProduct, MarketSource, ProductSources } from '../types'
import MarketHistoryChart from './MarketHistoryChart.vue'
import KnowledgeCenterDialog from '../../knowledge/components/KnowledgeCenterDialog.vue'

const props = defineProps<{ modelValue: boolean; product: MarketProduct | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; changed: [] }>()
const detail = ref<ProductSources | null>(null)
const history = ref<HistoryPoint[]>([])
const loading = ref(false)
const error = ref('')
const notice = ref('')
const addOpen = ref(false)
const editOpen = ref(false)
const manualOpen = ref(false)
const validationOpen = ref(false)
const knowledgeOpen = ref(false)
const manualSource = ref<MarketSource | null>(null)
const validationSource = ref<MarketSource | null>(null)
const editSource = ref<MarketSource | null>(null)
const manualPrice = ref<number | null>(null)
const manualNote = ref('')
const sourceBusyId = ref<number | null>(null)
const validationForm = ref({ ars_confirmed: false, argentina_delivery_confirmed: false, evidence_note: '' })
const form = ref({ source_name: '', url: '', source_type: 'static' as 'static' | 'dynamic' | 'manual', is_mandatory: false, attested_argentina_delivery: false })
const editForm = ref({ source_name: '', url: '', source_type: 'static' as 'static' | 'dynamic' | 'manual', is_mandatory: false })
let pollTimer: number | undefined
let disposed = false

async function load() {
  if (!props.product) return
  loading.value = true
  error.value = ''
  try {
    const [sources, points] = await Promise.all([getProductSources(props.product.product_id), getMarketHistory(props.product.product_id)])
    detail.value = sources
    history.value = points
  } catch (cause) { error.value = getHttpErrorMessage(cause) } finally { loading.value = false }
}
watch(() => [props.modelValue, props.product?.product_id], ([open]) => { if (open) void load() })
onBeforeUnmount(() => { disposed = true; if (pollTimer !== undefined) window.clearTimeout(pollTimer) })

async function add() { if (!props.product) return; try { await addMarketSource(props.product.product_id, { ...form.value, url: form.value.url.trim() || null }); addOpen.value = false; form.value = { source_name: '', url: '', source_type: 'static', is_mandatory: false, attested_argentina_delivery: false }; await load(); emit('changed') } catch (cause) { error.value = getHttpErrorMessage(cause) } }
async function remove(source: MarketSource) { if (!confirm(`¿Archivar ${source.source_name}? Podrás restaurarla después.`)) return; try { await deleteMarketSource(source.id); await load(); emit('changed') } catch (cause) { error.value = getHttpErrorMessage(cause) } }
async function restore(source: MarketSource) { try { await restoreMarketSource(source.id); await load(); emit('changed') } catch (cause) { error.value = getHttpErrorMessage(cause) } }
watch(editSource, (source) => { if (source) editForm.value = { source_name: source.source_name, url: source.url ?? '', source_type: source.source_type, is_mandatory: source.is_mandatory } })
async function saveEdit() { if (!editSource.value) return; try { await updateMarketSource(editSource.value.id, { ...editForm.value, url: editForm.value.source_type === 'manual' ? null : editForm.value.url.trim() }); editOpen.value = false; await load(); emit('changed') } catch (cause) { error.value = getHttpErrorMessage(cause) } }
function observe(source: MarketSource) { manualSource.value = source; manualPrice.value = source.last_price; manualNote.value = ''; manualOpen.value = true }
async function saveObservation() { if (!manualSource.value || !manualPrice.value) return; try { await createManualObservation(manualSource.value.id, manualPrice.value, manualNote.value || undefined); manualOpen.value = false; await load(); emit('changed') } catch (cause) { error.value = getHttpErrorMessage(cause) } }
async function revalidate(source: MarketSource) { try { await revalidateMarketSource(source.id); await load() } catch (cause) { error.value = getHttpErrorMessage(cause) } }
async function forceRediscovery() { if (!props.product) return; loading.value = true; try { await refreshProduct(props.product.product_id, true); notice.value = 'Redescubrimiento encolado.'; error.value = ''; emit('changed') } catch (cause) { error.value = getHttpErrorMessage(cause) } finally { loading.value = false } }

function scheduleJobPoll(jobId: string) {
  if (disposed) return
  pollTimer = window.setTimeout(async () => {
    try {
      const job = await getMarketJob(jobId)
      if (['partial', 'succeeded', 'failed', 'cancelled'].includes(job.status)) {
        sourceBusyId.value = null
        notice.value = job.status === 'succeeded' ? 'Detección finalizada; se actualizó la captura.' : 'La detección terminó sin un precio efectivo. Revisá el diagnóstico de la fuente.'
        await load(); emit('changed'); return
      }
      scheduleJobPoll(jobId)
    } catch (cause) { sourceBusyId.value = null; error.value = getHttpErrorMessage(cause) }
  }, 1000)
}
async function forcePriceDetection(source: MarketSource) { sourceBusyId.value = source.id; error.value = ''; notice.value = ''; try { const queued = await forceDetectMarketSourcePrice(source.id); notice.value = `Detección de precio encolada para ${source.source_name}.`; scheduleJobPoll(queued.job_id) } catch (cause) { sourceBusyId.value = null; error.value = getHttpErrorMessage(cause) } }
function openValidation(source: MarketSource) { validationSource.value = source; validationForm.value = { ars_confirmed: source.ars_confirmed === true, argentina_delivery_confirmed: source.argentina_delivery_confirmed === true, evidence_note: '' }; validationOpen.value = true }
async function saveValidation() {
  if (!validationSource.value) return
  sourceBusyId.value = validationSource.value.id
  try {
    const result = await manuallyValidateMarketSource(validationSource.value.id, validationForm.value)
    validationOpen.value = false
    notice.value = result.is_active ? 'Fuente validada y habilitada para el promedio.' : result.requires_price_detection ? 'Validación guardada. Falta detectar un precio para habilitar la fuente.' : 'Validación guardada; la fuente continúa en cuarentena.'
    await load(); emit('changed')
  } catch (cause) { error.value = getHttpErrorMessage(cause) } finally { sourceBusyId.value = null }
}
const allSources = () => [...(detail.value?.mandatory ?? []), ...(detail.value?.additional ?? []), ...(detail.value?.quarantined ?? [])]
const money = (value: number | null | undefined) => value == null ? '—' : `$ ${value.toLocaleString('es-AR', { minimumFractionDigits: 2 })}`
</script>

<template>
  <v-navigation-drawer :model-value="modelValue" location="right" temporary width="720" @update:model-value="emit('update:modelValue',$event)">
    <v-toolbar><v-toolbar-title>{{ product?.preferred_name || 'Mercado' }}</v-toolbar-title><v-btn icon="mdi-close" @click="emit('update:modelValue',false)" /></v-toolbar>
    <div class="pa-5">
      <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{ error }}</v-alert>
      <v-alert v-if="notice" type="info" closable variant="tonal" class="mb-4" @click:close="notice=''">{{ notice }}</v-alert>
      <v-progress-linear v-if="loading" indeterminate class="mb-4" />
      <v-row v-if="detail">
        <v-col cols="4"><v-card variant="tonal"><v-card-text><div class="text-caption">Venta</div><strong>{{ money(detail.sale_price) }}</strong></v-card-text></v-card></v-col>
        <v-col cols="4"><v-card variant="tonal"><v-card-text><div class="text-caption">Promedio</div><strong>{{ money(detail.market_price_reference) }}</strong></v-card-text></v-card></v-col>
        <v-col cols="4"><v-card variant="tonal"><v-card-text><div class="text-caption">Rango</div><strong>{{ money(detail.market_price_min) }} – {{ money(detail.market_price_max) }}</strong></v-card-text></v-card></v-col>
      </v-row>
      <div class="d-flex flex-wrap ga-2 my-4"><v-btn color="primary" prepend-icon="mdi-bookshelf" @click="knowledgeOpen=true">Conocimiento</v-btn><v-btn color="primary" prepend-icon="mdi-plus" variant="tonal" @click="addOpen=true">Agregar Mercado</v-btn><v-btn variant="tonal" prepend-icon="mdi-web-sync" @click="forceRediscovery">Forzar redescubrimiento</v-btn></div>
      <v-list lines="three">
        <v-list-item v-for="source in allSources()" :key="source.id">
          <template #prepend><v-icon :color="source.validation_status==='rejected'?'error':source.validation_status==='warning'?'warning':'success'" icon="mdi-web" /></template>
          <v-list-item-title><a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer" class="text-decoration-none">{{ source.source_name }}</a><span v-else>{{ source.source_name }}</span><v-chip size="x-small" class="ml-1">{{ source.origin==='market_discovery'?'automática':source.source_type }}</v-chip><v-chip v-if="!source.is_active" size="x-small" color="warning" class="ml-1">cuarentena</v-chip></v-list-item-title>
          <v-list-item-subtitle>{{ money(source.last_price) }} · {{ source.validation_status }} · {{ source.last_checked_at ? new Date(source.last_checked_at).toLocaleString('es-AR') : 'sin captura' }}<br><a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer" class="source-url">{{ source.url }}</a><span v-else>Fuente manual sin URL</span><span v-if="source.last_error_message" class="text-error"> · {{ source.last_error_message }}</span></v-list-item-subtitle>
          <template #append><div class="d-flex"><v-btn v-if="source.url && source.source_type!=='manual'" icon="mdi-radar" title="Forzar detección de precio" variant="text" :loading="sourceBusyId===source.id" @click="forcePriceDetection(source)" /><v-btn v-if="source.url && source.source_type!=='manual'" icon="mdi-clipboard-check-outline" title="Validar manualmente" variant="text" @click="openValidation(source)" /><v-btn icon="mdi-currency-usd" title="Cargar precio manual" variant="text" :disabled="!source.is_active" @click="observe(source)" /><v-btn icon="mdi-shield-refresh" title="Revalidar" variant="text" @click="revalidate(source)" /><v-btn icon="mdi-archive" title="Archivar" color="error" variant="text" @click="remove(source)" /></div></template>
        </v-list-item>
      </v-list>
      <v-card v-if="detail?.archived.length" class="my-4" variant="tonal"><v-card-title>Fuentes archivadas</v-card-title><v-list><v-list-item v-for="source in detail.archived" :key="source.id" :title="source.source_name" :subtitle="source.url || 'Fuente manual'"><template #append><v-btn prepend-icon="mdi-restore" variant="text" @click="restore(source)">Restaurar</v-btn></template></v-list-item></v-list></v-card>
      <v-card class="mt-4"><v-card-title>Histórico del promedio</v-card-title><v-card-text><MarketHistoryChart :items="history" /></v-card-text></v-card>
    </div>
  </v-navigation-drawer>
  <v-dialog v-model="validationOpen" max-width="600"><v-card><v-card-title>Validar fuente · {{ validationSource?.source_name }}</v-card-title><v-card-text><v-alert type="info" variant="tonal" class="mb-4">La fuente sólo se incorpora al promedio cuando ambas condiciones están confirmadas y existe un precio capturado.</v-alert><v-checkbox v-model="validationForm.ars_confirmed" label="Confirmo que el precio está expresado en ARS" /><v-checkbox v-model="validationForm.argentina_delivery_confirmed" label="Confirmo entrega disponible en Argentina" /><v-textarea v-model="validationForm.evidence_note" label="Evidencia o nota de auditoría" rows="3" counter="1000" /></v-card-text><v-card-actions><v-spacer/><v-btn @click="validationOpen=false">Cancelar</v-btn><v-btn color="primary" :disabled="validationForm.evidence_note.trim().length<10" :loading="sourceBusyId===validationSource?.id" @click="saveValidation">Guardar validación</v-btn></v-card-actions></v-card></v-dialog>
  <v-dialog v-model="addOpen" max-width="600"><v-card><v-card-title>Nueva fuente</v-card-title><v-card-text><v-text-field v-model="form.source_name" label="Competidor" /><v-select v-model="form.source_type" :items="[{title:'Estática',value:'static'},{title:'Dinámica / Chromium',value:'dynamic'},{title:'Manual libre',value:'manual'}]" label="Tipo" /><v-text-field v-if="form.source_type!=='manual'" v-model="form.url" label="URL" /><v-switch v-model="form.is_mandatory" label="Fuente obligatoria" /><v-checkbox v-if="form.source_type==='manual'" v-model="form.attested_argentina_delivery" label="Declaro que vende en ARS y entrega en Argentina" /></v-card-text><v-card-actions><v-spacer/><v-btn @click="addOpen=false">Cancelar</v-btn><v-btn color="primary" :disabled="!form.source_name.trim() || (form.source_type!=='manual'&&!form.url.trim())" @click="add">Crear</v-btn></v-card-actions></v-card></v-dialog>
  <v-dialog v-model="editOpen" max-width="600"><template #activator="{ props: activatorProps }"><v-btn v-if="modelValue && allSources().length" v-bind="activatorProps" class="market-edit-source" prepend-icon="mdi-pencil" position="fixed" location="bottom right">Editar fuente</v-btn></template><v-card><v-card-title>Editar fuente</v-card-title><v-card-text><v-select v-model="editSource" :items="allSources()" item-title="source_name" return-object label="Fuente" /><v-text-field v-model="editForm.source_name" label="Competidor" /><v-select v-model="editForm.source_type" :items="[{title:'Estática',value:'static'},{title:'Dinámica / Chromium',value:'dynamic'},{title:'Manual libre',value:'manual'}]" label="Tipo" /><v-text-field v-if="editForm.source_type!=='manual'" v-model="editForm.url" label="URL" /><v-switch v-model="editForm.is_mandatory" label="Fuente obligatoria" /></v-card-text><v-card-actions><v-spacer/><v-btn @click="editOpen=false">Cancelar</v-btn><v-btn color="primary" :disabled="!editSource || !editForm.source_name.trim() || (editForm.source_type!=='manual'&&!editForm.url.trim())" @click="saveEdit">Guardar</v-btn></v-card-actions></v-card></v-dialog>
  <v-dialog v-model="manualOpen" max-width="520"><v-card><v-card-title>Precio manual · {{ manualSource?.source_name }}</v-card-title><v-card-text><v-text-field v-model.number="manualPrice" type="number" min="0.01" step="0.01" prefix="$" suffix="ARS" label="Precio" /><v-textarea v-model="manualNote" label="Nota de auditoría" rows="2" /></v-card-text><v-card-actions><v-spacer/><v-btn @click="manualOpen=false">Cancelar</v-btn><v-btn color="primary" :disabled="!manualPrice || manualPrice<=0" @click="saveObservation">Guardar observación</v-btn></v-card-actions></v-card></v-dialog>
  <KnowledgeCenterDialog v-if="product" v-model="knowledgeOpen" :canonical-product-id="product.product_id" initial-label="market" @changed="load" />
</template>

<style scoped>
.source-url { color: inherit; overflow-wrap: anywhere; }
</style>
