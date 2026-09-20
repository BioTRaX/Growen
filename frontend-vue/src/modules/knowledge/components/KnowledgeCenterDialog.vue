<!-- NG-HEADER: Nombre de archivo: KnowledgeCenterDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/knowledge/components/KnowledgeCenterDialog.vue -->
<!-- NG-HEADER: Descripción: Centro compartido de fuentes, medios, hechos, historial e IA. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { VDialog } from 'vuetify/components'
import { getHttpErrorMessage } from '../../../services/http'
import {
  archiveKnowledge,
  createKnowledge,
  getKnowledge,
  getKnowledgeCapabilities,
  getKnowledgeFacts,
  getKnowledgeHistory,
  getKnowledgeJobs,
  processKnowledge,
  restoreKnowledge,
  updateKnowledge,
  uploadKnowledge,
} from '../api/knowledge'
import type { KnowledgeAsset, KnowledgeAssetType, KnowledgeCapability, KnowledgeEvent, KnowledgeFact, KnowledgeJob, KnowledgeResponse } from '../types'

const props = withDefaults(defineProps<{
  modelValue?: boolean
  canonicalProductId: number
  initialLabel?: string | null
  embedded?: boolean
}>(), { modelValue: false, initialLabel: null, embedded: false })
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; changed: [] }>()
const { smAndDown } = useDisplay()
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const tab = ref('sources')
const includeArchived = ref(false)
const labelFilter = ref<string | null>(props.initialLabel)
const data = ref<KnowledgeResponse | null>(null)
const capabilities = ref<KnowledgeCapability[]>([])
const facts = ref<KnowledgeFact[]>([])
const history = ref<KnowledgeEvent[]>([])
const jobs = ref<KnowledgeJob[]>([])
const editOpen = ref(false)
const uploadOpen = ref(false)
const editing = ref<KnowledgeAsset | null>(null)
const uploadFile = ref<File | null>(null)
const labels = [
  { title: 'Fabricante', value: 'manufacturer' },
  { title: 'Proveedor', value: 'supplier' },
  { title: 'Mercado', value: 'market' },
  { title: 'Manual', value: 'manual' },
  { title: 'Catálogo', value: 'catalog' },
  { title: 'MSDS', value: 'msds' },
  { title: 'Oficial', value: 'official' },
  { title: 'Otro', value: 'other' },
]
const form = ref({
  title: '',
  asset_type: 'web' as KnowledgeAssetType,
  url: '',
  labels: [] as string[],
  capabilities: [] as string[],
  exclude_from_enrichment: false,
  market_is_active: true,
  market_is_mandatory: false,
  market_source_type: 'static' as 'static' | 'dynamic',
  market_argentina_delivery_confirmed: false,
})

const filtered = computed(() => (data.value?.items ?? []).filter((asset) =>
  (!labelFilter.value || asset.labels.includes(labelFilter.value))
  && (includeArchived.value || asset.status !== 'archived'),
))
const byType = (type: KnowledgeAssetType) => filtered.value.filter((asset) => asset.asset_type === type)
const confidenceColor = (value: number) => value >= 90 ? 'success' : value >= 70 ? 'warning' : 'error'
const labelTitle = (value: string) => labels.find((item) => item.value === value)?.title ?? value

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [knowledge, capabilityItems, factItems, eventItems, jobItems] = await Promise.all([
      getKnowledge(props.canonicalProductId, true),
      getKnowledgeCapabilities(),
      getKnowledgeFacts(props.canonicalProductId),
      getKnowledgeHistory(props.canonicalProductId),
      getKnowledgeJobs(props.canonicalProductId),
    ])
    data.value = knowledge
    capabilities.value = capabilityItems
    facts.value = factItems
    history.value = eventItems
    jobs.value = jobItems
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo cargar el conocimiento')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.embedded, props.canonicalProductId] as const,
  ([open, embedded]) => {
    if (open || embedded) {
      labelFilter.value = props.initialLabel
      void load()
    }
  },
  { immediate: true },
)

function openCreate(type: KnowledgeAssetType = 'web'): void {
  editing.value = null
  form.value = {
    title: '',
    asset_type: type,
    url: '',
    labels: props.initialLabel ? [props.initialLabel] : [],
    capabilities: [],
    exclude_from_enrichment: false,
    market_is_active: true,
    market_is_mandatory: false,
    market_source_type: 'static',
    market_argentina_delivery_confirmed: false,
  }
  editOpen.value = true
}

function openEdit(asset: KnowledgeAsset): void {
  editing.value = asset
  form.value = {
    title: asset.title,
    asset_type: asset.asset_type,
    url: asset.locations.find((item) => item.is_primary)?.url ?? '',
    labels: [...asset.labels],
    capabilities: [...asset.capabilities],
    exclude_from_enrichment: asset.exclude_from_enrichment,
    market_is_active: asset.market?.is_active ?? true,
    market_is_mandatory: asset.market?.is_mandatory ?? false,
    market_source_type: asset.market?.source_type === 'dynamic' ? 'dynamic' : 'static',
    market_argentina_delivery_confirmed: asset.market?.argentina_delivery_confirmed ?? false,
  }
  editOpen.value = true
}

async function save(): Promise<void> {
  saving.value = true
  error.value = ''
  try {
    if (editing.value) {
      await updateKnowledge(props.canonicalProductId, editing.value, form.value)
    } else {
      await createKnowledge(props.canonicalProductId, {
        ...form.value,
        url: form.value.url.trim() || null,
      })
    }
    editOpen.value = false
    await load()
    emit('changed')
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo guardar el activo')
  } finally {
    saving.value = false
  }
}

async function archive(asset: KnowledgeAsset): Promise<void> {
  if (!confirm(`¿Archivar “${asset.title}”? El histórico se conservará.`)) return
  try {
    await archiveKnowledge(props.canonicalProductId, asset.id)
    await load()
    emit('changed')
  } catch (cause) {
    error.value = getHttpErrorMessage(cause)
  }
}

async function restore(asset: KnowledgeAsset): Promise<void> {
  try {
    await restoreKnowledge(props.canonicalProductId, asset.id)
    await load()
    emit('changed')
  } catch (cause) {
    error.value = getHttpErrorMessage(cause)
  }
}

async function process(asset: KnowledgeAsset): Promise<void> {
  try {
    await processKnowledge(props.canonicalProductId, asset.id)
    await load()
  } catch (cause) {
    error.value = getHttpErrorMessage(cause)
  }
}

async function upload(): Promise<void> {
  if (!uploadFile.value || !form.value.title.trim() || !form.value.labels.length) return
  saving.value = true
  try {
    await uploadKnowledge(
      props.canonicalProductId,
      uploadFile.value,
      form.value.title,
      form.value.labels,
      form.value.capabilities,
    )
    uploadOpen.value = false
    uploadFile.value = null
    await load()
    emit('changed')
  } catch (cause) {
    error.value = getHttpErrorMessage(cause)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <component
    :is="embedded ? 'div' : VDialog"
    v-bind="embedded ? { class: 'knowledge-center-page' } : {
      fullscreen: smAndDown,
      modelValue,
      class: 'knowledge-center-dialog',
      maxWidth: 1040,
      scrollable: true,
      width: 'calc(100% - 64px)',
    }"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card :class="embedded ? 'knowledge-page-card' : 'knowledge-dialog-card'" :flat="embedded">
      <v-toolbar color="surface">
        <v-btn v-if="!embedded" icon="mdi-close" @click="emit('update:modelValue', false)" />
        <v-toolbar-title>Conocimiento del producto</v-toolbar-title>
        <v-chip v-if="data" class="mr-4" color="primary" variant="tonal">{{ data.summary.total }} activos</v-chip>
      </v-toolbar>
      <v-progress-linear v-if="loading" indeterminate />
      <v-alert v-if="error" class="ma-4" closable type="error" @click:close="error = ''">{{ error }}</v-alert>

      <v-tabs v-model="tab" class="knowledge-dialog-tabs px-4" show-arrows>
        <v-tab value="sources">Fuentes</v-tab>
        <v-tab value="documents">Documentos</v-tab>
        <v-tab value="images">Imágenes</v-tab>
        <v-tab value="videos">Videos</v-tab>
        <v-tab value="facts">Hechos</v-tab>
        <v-tab value="history">Historial</v-tab>
        <v-tab value="ai">IA</v-tab>
      </v-tabs>

      <v-window v-model="tab" class="knowledge-dialog-content">
        <v-window-item value="sources">
          <div class="pa-5">
            <div class="d-flex flex-wrap align-center ga-3 mb-4">
              <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreate()">Agregar fuente</v-btn>
              <v-btn prepend-icon="mdi-upload" variant="tonal" @click="uploadOpen = true">Subir activo</v-btn>
              <v-select v-model="labelFilter" clearable density="compact" hide-details :items="labels" label="Etiqueta" max-width="260" />
              <v-switch v-model="includeArchived" density="compact" hide-details label="Mostrar archivadas" />
            </div>
            <v-row dense>
              <v-col v-for="asset in filtered" :key="asset.id" cols="12">
                <v-card :variant="asset.status === 'archived' ? 'outlined' : 'elevated'">
                  <v-card-title class="knowledge-card-title d-flex align-start ga-2">
                    <span class="knowledge-card-heading">{{ asset.title }}</span>
                    <v-spacer />
                    <v-chip :color="confidenceColor(asset.trust_score)" size="small">{{ asset.trust_score.toFixed(0) }}</v-chip>
                  </v-card-title>
                  <v-card-subtitle>{{ asset.asset_type }} · {{ asset.status }} · {{ asset.origin }}</v-card-subtitle>
                  <v-card-text>
                    <div class="d-flex flex-wrap ga-1 mb-3">
                      <v-chip v-for="label in asset.labels" :key="label" size="small">{{ labelTitle(label) }}</v-chip>
                      <v-chip v-if="asset.exclude_from_enrichment" color="warning" size="small">Excluida de Enrich</v-chip>
                    </div>
                    <div class="d-flex flex-wrap ga-1 mb-3">
                      <v-chip v-for="capability in asset.capabilities" :key="capability" size="x-small" variant="outlined">{{ capability }}</v-chip>
                    </div>
                    <div v-for="location in asset.locations" :key="location.id" class="knowledge-location text-body-2">
                      <a v-if="location.url" :href="location.url" rel="noopener noreferrer" target="_blank">{{ location.url }}</a>
                      <span v-else>{{ location.storage_path }}</span>
                      · {{ location.status }} · v{{ location.content_version }}
                    </div>
                    <v-alert v-if="asset.market" class="mt-3" density="compact" type="info" variant="tonal">
                      Mercado: {{ asset.market.validation_status }} · {{ asset.market.is_active ? 'activa' : 'inactiva' }}
                    </v-alert>
                  </v-card-text>
                  <v-card-actions class="flex-wrap">
                    <v-btn prepend-icon="mdi-cog-play" size="small" variant="text" @click="process(asset)">Procesar</v-btn>
                    <v-btn v-if="asset.status !== 'archived'" prepend-icon="mdi-pencil" size="small" variant="text" @click="openEdit(asset)">Editar</v-btn>
                    <v-btn v-if="asset.status !== 'archived'" color="error" prepend-icon="mdi-archive" size="small" variant="text" @click="archive(asset)">Archivar</v-btn>
                    <v-btn v-else prepend-icon="mdi-restore" size="small" variant="text" @click="restore(asset)">Restaurar</v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
            <v-empty-state v-if="!filtered.length && !loading" icon="mdi-bookshelf" title="Sin conocimiento para este filtro" />
          </div>
        </v-window-item>

        <v-window-item value="documents"><div class="pa-5"><v-list><v-list-item v-for="asset in byType('document')" :key="asset.id" :title="asset.title" :subtitle="`${asset.status} · confianza ${asset.trust_score}`" prepend-icon="mdi-file-document" /></v-list></div></v-window-item>
        <v-window-item value="images"><div class="pa-5 d-flex flex-wrap ga-4"><v-card v-for="asset in byType('image')" :key="asset.id" width="280"><v-card-title>{{ asset.title }}</v-card-title><v-card-subtitle>{{ asset.locations[0]?.metadata || 'Pendiente de procesar' }}</v-card-subtitle></v-card></div></v-window-item>
        <v-window-item value="videos"><div class="pa-5"><v-list><v-list-item v-for="asset in byType('video')" :key="asset.id" :title="asset.title" :subtitle="JSON.stringify(asset.locations[0]?.metadata || {})" prepend-icon="mdi-video" /></v-list></div></v-window-item>
        <v-window-item value="facts"><div class="pa-5"><v-table><thead><tr><th>Hecho</th><th>Capacidad</th><th>Valor</th><th>Confianza</th></tr></thead><tbody><tr v-for="fact in facts" :key="fact.id"><td>{{ fact.fact_key }}</td><td>{{ fact.capability }}</td><td><code>{{ JSON.stringify(fact.value) }}</code></td><td>{{ (fact.confidence * 100).toFixed(1) }}%</td></tr></tbody></v-table></div></v-window-item>
        <v-window-item value="history"><div class="pa-5"><v-timeline density="compact"><v-timeline-item v-for="event in history" :key="event.id" size="small"><strong>{{ event.event_type }}</strong><div>{{ new Date(event.created_at).toLocaleString('es-AR') }} · usuario {{ event.actor_user_id ?? 'sistema' }}</div><code>{{ JSON.stringify(event.payload) }}</code></v-timeline-item></v-timeline></div></v-window-item>
        <v-window-item value="ai"><div class="pa-5"><v-list><v-list-item v-for="job in jobs" :key="job.id" :title="`${job.status} · activo ${job.asset_id}`" :subtitle="job.error || job.stage || job.created_at" prepend-icon="mdi-robot" /></v-list></div></v-window-item>
      </v-window>
    </v-card>
  </component>

  <v-dialog v-model="editOpen" max-width="760" scrollable width="calc(100% - 32px)">
    <v-card>
      <v-card-title>{{ editing ? 'Editar conocimiento' : 'Nuevo conocimiento' }}</v-card-title>
      <v-card-text>
        <v-text-field v-model="form.title" label="Título" />
        <v-select v-model="form.asset_type" :disabled="!!editing" :items="['web', 'document', 'image', 'video']" label="Tipo" />
        <v-text-field v-if="!editing" v-model="form.url" label="URL" />
        <v-select v-model="form.labels" chips closable-chips multiple :items="labels" label="Etiquetas" />
        <v-select v-model="form.capabilities" chips closable-chips item-title="name" item-value="code" multiple :items="capabilities" label="Capacidades" />
        <v-checkbox v-model="form.exclude_from_enrichment" label="Excluir de Enrich" />
        <v-card v-if="form.labels.includes('market')" class="mt-3" variant="tonal">
          <v-card-title class="text-subtitle-1">Configuración Mercado</v-card-title>
          <v-card-text>
            <v-select v-model="form.market_source_type" :items="[{ title: 'HTML estático', value: 'static' }, { title: 'Sitio dinámico', value: 'dynamic' }]" label="Tipo de lectura" />
            <v-checkbox v-model="form.market_is_active" label="Perfil activo" />
            <v-checkbox v-model="form.market_is_mandatory" label="Fuente obligatoria" />
            <v-checkbox v-model="form.market_argentina_delivery_confirmed" label="Confirmo precios ARS y entrega en Argentina" />
            <v-alert v-if="!form.market_argentina_delivery_confirmed" density="compact" type="warning" variant="tonal">
              La fuente no participará del scraping ni del promedio hasta confirmar este requisito.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="editOpen = false">Cancelar</v-btn><v-btn color="primary" :disabled="!form.title.trim() || !form.labels.length" :loading="saving" @click="save">Guardar</v-btn></v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="uploadOpen" max-width="680" scrollable width="calc(100% - 32px)">
    <v-card>
      <v-card-title>Subir documento, imagen o video</v-card-title>
      <v-card-text>
        <v-text-field v-model="form.title" label="Título" />
        <v-file-input v-model="uploadFile" accept=".pdf,image/*,video/mp4,video/webm" label="Archivo" />
        <v-select v-model="form.labels" chips multiple :items="labels" label="Etiquetas" />
        <v-select v-model="form.capabilities" chips item-title="name" item-value="code" multiple :items="capabilities" label="Capacidades" />
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="uploadOpen = false">Cancelar</v-btn><v-btn color="primary" :disabled="!uploadFile || !form.title.trim() || !form.labels.length" :loading="saving" @click="upload">Subir</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.knowledge-dialog-card {
  display: flex;
  flex-direction: column;
  height: min(78vh, 760px);
  overflow: hidden;
}
.knowledge-page-card { min-height: 60vh; }
.knowledge-center-page { width: 100%; }
.knowledge-dialog-tabs { flex: 0 0 auto; min-height: 48px; }
.knowledge-dialog-content { flex: 1 1 0; min-height: 0; overflow-y: auto; }
.knowledge-card-title { white-space: normal; }
.knowledge-card-heading { min-width: 0; overflow-wrap: anywhere; }
.knowledge-location { overflow-wrap: anywhere; word-break: break-word; }

@media (max-width: 600px) {
  .knowledge-dialog-card { height: 100%; }
}
</style>
