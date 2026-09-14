<!-- NG-HEADER: Nombre de archivo: CatalogAuditView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.vue -->
<!-- NG-HEADER: Descripción: Inicio, progreso e intervención del auditor autónomo de catálogo. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import {
  cancelCatalogAudit, createCatalogAudit, getCatalogAudit, getCatalogAuditPreflight,
  listCatalogAudits, resolveCatalogAuditItem, retryCatalogAudit,
} from '../api/catalogAudit'
import type { CatalogAuditItem, CatalogAuditOptions, CatalogAuditPreflight, CatalogAuditResolutionAction, CatalogAuditRun } from '../types'

const route = useRoute()
const auth = useAuthStore()
const selectedIds = String(route.query.canonical_ids ?? '').split(',').map(Number).filter((id) => Number.isInteger(id) && id > 0)
const options = ref<CatalogAuditOptions>({
  scope: selectedIds.length ? 'selected' : 'pending',
  canonical_product_ids: selectedIds.length ? [...new Set(selectedIds)] : undefined,
  include_orphans: true,
  mode: 'full',
  enrich_missing: true,
  auto_fix: false,
})
const preflight = ref<CatalogAuditPreflight>()
const history = ref<CatalogAuditRun[]>([])
const current = ref<CatalogAuditRun>()
const loading = ref(false)
const error = ref('')
const resolutionItem = ref<CatalogAuditItem>()
const resolutionAction = ref<CatalogAuditResolutionAction>('reaudit')
const resolutionNote = ref('')
const resolutionClass = ref('')
const resolutionCorrections = ref('{}')
const resolutionRevision = ref<number>()
const resolutionVersionId = ref<number>()
const resolving = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined

const active = computed(() => current.value && ['queued', 'running', 'waiting_enrich'].includes(current.value.status))
const progress = computed(() => current.value?.total_items ? Math.round(current.value.processed_items * 100 / current.value.total_items) : 0)
const canStart = computed(() => Boolean(preflight.value?.worker.ok)
  && (!options.value.enrich_missing || Boolean(preflight.value?.enrichment_worker.ok))
  && (options.value.mode === 'deterministic_only' || Boolean(preflight.value?.ollama.ok)))
const statusColors: Record<string, string> = {
  clean: 'success', auto_fixed: 'success', skipped_unchanged: 'info', canonical_required: 'warning',
  waiting_enrich: 'info', needs_review: 'warning', quarantined: 'error', failed: 'error', cancelled: 'grey',
}

function stopPolling(): void {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = undefined
  controller?.abort()
  controller = undefined
}

async function loadCurrent(runId: string): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  try {
    current.value = await getCatalogAudit(runId, controller.signal)
    if (['queued', 'running', 'waiting_enrich'].includes(current.value.status)) {
      pollTimer = setTimeout(() => void loadCurrent(runId), 3000)
    } else {
      history.value = await listCatalogAudits()
    }
  } catch (cause) {
    if ((cause as Error)?.name !== 'CanceledError') error.value = getHttpErrorMessage(cause)
  }
}

async function refresh(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [health, runs] = await Promise.all([getCatalogAuditPreflight(), listCatalogAudits()])
    preflight.value = health
    history.value = runs
    const running = runs.find((run) => ['queued', 'running', 'waiting_enrich'].includes(run.status))
    const target = running ?? current.value ?? runs[0]
    if (target) await loadCurrent(target.run_id)
  } catch (cause) { error.value = getHttpErrorMessage(cause) }
  finally { loading.value = false }
}

async function start(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const created = await createCatalogAudit(options.value)
    await loadCurrent(created.run_id)
  } catch (cause) { error.value = getHttpErrorMessage(cause) }
  finally { loading.value = false }
}

async function cancel(): Promise<void> {
  if (!current.value) return
  await cancelCatalogAudit(current.value.run_id)
  await loadCurrent(current.value.run_id)
}

async function retry(): Promise<void> {
  if (!current.value) return
  await retryCatalogAudit(current.value.run_id)
  await loadCurrent(current.value.run_id)
}

function openResolution(item: CatalogAuditItem, action: typeof resolutionAction.value): void {
  resolutionItem.value = item
  resolutionAction.value = action
  resolutionNote.value = ''
  resolutionClass.value = item.product_class ?? ''
  resolutionCorrections.value = JSON.stringify(item.corrections?.[0] ?? {}, null, 2)
  resolutionRevision.value = item.content_revision ?? undefined
  resolutionVersionId.value = item.content_versions?.[0]?.version_id
}

async function resolveItem(): Promise<void> {
  if (!current.value || !resolutionItem.value) return
  resolving.value = true
  error.value = ''
  try {
    let corrections: Record<string, unknown> | undefined
    if (resolutionAction.value === 'apply_correction') {
      const parsed: unknown = JSON.parse(resolutionCorrections.value)
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('La corrección debe ser un objeto JSON.')
      corrections = parsed as Record<string, unknown>
    }
    const result = await resolveCatalogAuditItem(current.value.run_id, resolutionItem.value.item_id, {
      action: resolutionAction.value,
      note: resolutionNote.value,
      product_class: resolutionClass.value || undefined,
      corrections,
      expected_content_revision: ['apply_correction', 'restore_version'].includes(resolutionAction.value) ? resolutionRevision.value : undefined,
      version_id: resolutionAction.value === 'restore_version' ? resolutionVersionId.value : undefined,
    })
    resolutionItem.value = undefined
    await loadCurrent(result.new_run_id ?? current.value.run_id)
  } catch (cause) {
    error.value = cause instanceof SyntaxError ? 'El JSON de correcciones no es válido.' : getHttpErrorMessage(cause)
  } finally {
    resolving.value = false
  }
}

onMounted(() => void refresh())
onBeforeUnmount(stopPolling)
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-6">
      <div><h1 class="text-h4">Auditor autónomo de catálogo</h1><p class="text-medium-emphasis mb-0">Auditoría persistente por versión efectiva, independiente de Enrich.</p></div>
      <v-btn :loading="loading" prepend-icon="mdi-refresh" variant="tonal" @click="refresh">Actualizar</v-btn>
    </div>
    <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>

    <v-row class="mb-2">
      <v-col cols="12" md="4"><v-alert :type="preflight?.worker.ok ? 'success' : 'error'" variant="tonal"><strong>{{ preflight?.worker.ok ? 'Worker disponible' : 'Worker no disponible' }}</strong><div class="text-caption">Cola: {{ preflight?.queue ?? 'catalog_audit' }}</div></v-alert></v-col>
      <v-col cols="12" md="4"><v-alert :type="preflight?.ollama.ok ? 'success' : 'warning'" variant="tonal"><strong>Ollama · {{ preflight?.ollama.model ?? 'llama3.1:8b' }}</strong><div class="text-caption">{{ preflight?.ollama.ok ? 'Modelo listo para auditoría completa' : (preflight?.ollama.code ?? 'Preflight pendiente') }}</div></v-alert></v-col>
      <v-col cols="12" md="4"><v-alert :type="preflight?.enrichment_worker.ok ? 'success' : 'warning'" variant="tonal"><strong>Enrich independiente</strong><div class="text-caption">{{ preflight?.enrichment_worker.ok ? 'Disponible para contenido ausente' : 'No disponible; desactive Enrich faltante' }}</div></v-alert></v-col>
    </v-row>

    <v-card class="mb-6">
      <v-card-title>Configurar ejecución</v-card-title>
      <v-card-text><v-row>
        <v-col cols="12" md="3"><v-select v-model="options.scope" :disabled="active" :items="[{title:'Pendientes o cambiados',value:'pending'},{title:'Todo el catálogo',value:'all'},{title:'Selección recibida',value:'selected'}]" item-title="title" item-value="value" label="Alcance" /></v-col>
        <v-col cols="12" md="3"><v-select v-model="options.mode" :disabled="active" :items="[{title:'Completo · reglas + Ollama',value:'full'},{title:'Sólo determinista',value:'deterministic_only'}]" item-title="title" item-value="value" label="Modo" /></v-col>
        <v-col cols="12" md="6"><v-switch v-model="options.include_orphans" :disabled="active" color="primary" label="Reportar productos internos huérfanos" /><v-switch v-model="options.enrich_missing" :disabled="active" color="primary" label="Invocar Enrich sólo si falta contenido útil" /><v-switch v-if="auth.role === 'admin'" v-model="options.auto_fix" :disabled="active" color="warning" label="Autocorrección de alta confianza" /></v-col>
      </v-row>
      <v-alert v-if="options.scope === 'selected'" type="info" variant="tonal">Selección: {{ options.canonical_product_ids?.length ?? 0 }} canónico(s) únicos.</v-alert>
      </v-card-text>
      <v-card-actions><v-btn color="primary" :disabled="!canStart || Boolean(active)" :loading="loading" prepend-icon="mdi-clipboard-search-outline" @click="start">Iniciar auditoría</v-btn><span v-if="!canStart" class="text-caption text-error">El modo elegido no supera el preflight.</span></v-card-actions>
    </v-card>

    <v-card v-if="current" class="mb-6">
      <v-card-item :title="`Ejecución ${current.run_id.slice(0, 8)}`" :subtitle="`${current.status} · ${current.processed_items}/${current.total_items}`"><template #append><v-chip>{{ current.mode }}</v-chip></template></v-card-item>
      <v-card-text><v-progress-linear class="mb-4" color="primary" height="12" :model-value="progress" rounded /><div class="d-flex flex-wrap ga-5"><span>Limpios/reutilizados: {{ current.clean_items }}</span><span>Con tratamiento: {{ current.issue_items }}</span><span>Progreso: {{ progress }}%</span></div></v-card-text>
      <v-card-actions><v-btn v-if="active" color="error" variant="tonal" @click="cancel">Cancelar</v-btn><v-btn v-else-if="['failed','cancelled'].includes(current.status)" variant="tonal" @click="retry">Reanudar fallidos</v-btn></v-card-actions>
      <v-divider />
      <v-table density="compact"><thead><tr><th>Producto</th><th>Estado</th><th>Clase</th><th>Score</th><th>Tratamiento</th></tr></thead><tbody>
        <tr v-for="item in current.items ?? []" :key="item.item_id">
          <td><v-btn v-if="item.product_id" :to="`/productos/${item.product_id}`" size="small" variant="text">Interno #{{ item.product_id }}</v-btn><span v-else>Canónico #{{ item.canonical_product_id }}</span></td>
          <td><v-chip :color="statusColors[item.status] ?? 'grey'" size="small">{{ item.status }}</v-chip></td><td>{{ item.product_class ?? '—' }}</td><td>{{ item.score ?? '—' }}</td>
          <td class="py-2"><div class="d-flex flex-wrap ga-1">
            <v-btn v-if="item.status === 'canonical_required'" to="/productos" size="x-small" variant="tonal">Canonizar</v-btn>
            <v-btn v-if="['failed','needs_review'].includes(item.status)" size="x-small" variant="tonal" @click="openResolution(item, 'reaudit')">Reauditar</v-btn>
            <v-btn v-if="item.product_id && ['needs_review','quarantined'].includes(item.status)" :to="`/productos/${item.product_id}`" size="x-small" variant="tonal">Editar ficha</v-btn>
            <v-btn v-if="auth.role === 'admin' && item.status === 'needs_review'" size="x-small" variant="tonal" @click="openResolution(item, 'accept_exception')">Aceptar excepción</v-btn>
            <v-btn v-if="auth.role === 'admin' && item.status === 'needs_review'" size="x-small" variant="tonal" @click="openResolution(item, 'classification')">Corregir clase</v-btn>
            <v-btn v-if="auth.role === 'admin' && item.status === 'needs_review'" size="x-small" variant="tonal" @click="openResolution(item, 'apply_correction')">Aplicar corrección</v-btn>
            <v-btn v-if="auth.role === 'admin' && ['needs_review','quarantined'].includes(item.status) && item.content_versions.length" size="x-small" variant="tonal" @click="openResolution(item, 'restore_version')">Restaurar versión</v-btn>
            <v-btn v-if="auth.role === 'admin' && item.status === 'quarantined'" color="warning" size="x-small" variant="tonal" @click="openResolution(item, 'release_quarantine')">Liberar cuarentena</v-btn>
          </div></td>
        </tr>
      </tbody></v-table>
    </v-card>

    <v-card><v-card-title>Historial</v-card-title><v-list><v-list-item v-for="run in history" :key="run.run_id" :subtitle="`${run.processed_items}/${run.total_items} · ${run.created_at ? new Date(run.created_at).toLocaleString('es-AR') : ''}`" :title="`${run.run_id.slice(0, 8)} · ${run.status}`" @click="loadCurrent(run.run_id)" /></v-list></v-card>

    <v-dialog :model-value="Boolean(resolutionItem)" max-width="620" @update:model-value="!$event && (resolutionItem = undefined)"><v-card><v-card-title>Resolver ítem #{{ resolutionItem?.item_id }}</v-card-title><v-card-text>
      <v-select v-if="resolutionAction === 'classification'" v-model="resolutionClass" :items="['liquid','substrate','container','tent','weight_product','other']" label="Clasificación correcta" />
      <template v-if="resolutionAction === 'apply_correction'"><v-textarea v-model="resolutionCorrections" auto-grow label="Correcciones JSON" rows="5" /><v-number-input v-model="resolutionRevision" :min="0" label="Revisión de contenido esperada" /></template>
      <template v-if="resolutionAction === 'restore_version'"><v-select v-model="resolutionVersionId" :items="resolutionItem?.content_versions ?? []" item-title="origin" item-value="version_id" label="Versión a restaurar"><template #item="{ props, item }"><v-list-item v-bind="props" :subtitle="`Revisión ${item.raw.revision}`" /></template></v-select><v-number-input v-model="resolutionRevision" :min="0" label="Revisión de contenido esperada" /></template>
      <v-textarea v-model="resolutionNote" label="Motivo y evidencia" rows="4" />
    </v-card-text><v-card-actions><v-spacer /><v-btn variant="text" @click="resolutionItem = undefined">Cancelar</v-btn><v-btn color="primary" :disabled="resolutionNote.trim().length < 3" :loading="resolving" @click="resolveItem">Confirmar</v-btn></v-card-actions></v-card></v-dialog>
  </v-container>
</template>
