<!-- NG-HEADER: Nombre de archivo: ProductImagesView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/images/views/ProductImagesView.vue -->
<!-- NG-HEADER: Descripción: Gestor integral de imágenes: Sincronización con Drive, edición masiva y revisión de catálogo. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import {
  approveImage,
  cancelDriveRun,
  getDriveStatus,
  getGlobalLogo,
  getProductImages,
  listImageReviews,
  openDriveEvents,
  previewDriveSync,
  processProductImage,
  rejectImage,
  setPrimaryProductImage,
  startDriveRun,
  uploadGlobalLogo,
  type DrivePreviewItem,
  type DrivePreviewResponse,
  type ImageReview,
  type ProductImages,
} from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'
import { listProducts } from '../../products/api/products'
import type { ProductListItem } from '../../products/types'

// Pestaña activa
const activeTab = ref<'drive' | 'catalog' | 'reviews'>('drive')

// --- ESTADO GENERAL & CABECERA ---
const error = ref('')
const successMsg = ref('')
const loading = ref(false)
const logoInfo = ref<{ exists: boolean; url: string | null; width: number | null; height: number | null } | null>(null)
const uploadingLogo = ref(false)
const logoInputRef = ref<HTMLInputElement | null>(null)
const cacheTs = ref(Date.now())

// --- PESTAÑA 1: SINCRONIZACIÓN GOOGLE DRIVE ---
const DEFAULT_DRIVE_FOLDER_ID = '13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7'
const driveFolderId = ref(DEFAULT_DRIVE_FOLDER_ID)
const previewLoading = ref(false)
const previewData = ref<DrivePreviewResponse | null>(null)
const previewFilterStatus = ref<string>('all')
const previewSearchText = ref('')

// Sincronización en vivo
const syncStarting = ref(false)
const syncActive = ref(false)
const syncRunId = ref<string | null>(null)
const syncProgress = ref({
  status: 'idle',
  current: 0,
  total: 0,
  sku: '',
  filename: '',
  message: '',
  processed: 0,
  errors: 0,
  no_sku: 0,
})
let driveWs: WebSocket | null = null

// --- PESTAÑA 2: CATÁLOGO Y PROCESAMIENTO MASIVO ---
const productQuery = ref('')
const products = ref<ProductListItem[]>([])
const productsLoading = ref(false)
const selectedProductIds = ref<number[]>([])
const selectedSingleProduct = ref<ProductListItem | null>(null)
const singleProductImages = ref<ProductImages | null>(null)
const singleImagesLoading = ref(false)

// Proceso masivo en lote
const batchRunning = ref(false)
const batchAction = ref<'logo' | 'webp' | 'watermark'>('logo')
const batchProgress = ref({ current: 0, total: 0, currentName: '', logs: [] as string[] })
const batchCancelRequested = ref(false)

// --- PESTAÑA 3: COLA DE REVISIÓN ---
const reviewItems = ref<ImageReview[]>([])
const reviewProcessing = ref<number>()
const rejectDialog = ref(false)
const rejectTarget = ref<ImageReview>()
const rejectNote = ref('')

// --- COMPUTED PROPERTIES ---
const previewFilteredItems = computed(() => {
  if (!previewData.value?.items) return []
  return previewData.value.items.filter((item) => {
    if (previewFilterStatus.value !== 'all' && item.match_status !== previewFilterStatus.value) {
      return false
    }
    if (previewSearchText.value.trim()) {
      const q = previewSearchText.value.toLowerCase().trim()
      const inFilename = item.filename.toLowerCase().includes(q)
      const inSku = (item.sku_extracted || '').toLowerCase().includes(q)
      const inProd = (item.product_title || '').toLowerCase().includes(q)
      if (!inFilename && !inSku && !inProd) return false
    }
    return true
  })
})

const isAllSelected = computed(() => {
  return products.value.length > 0 && products.value.every(p => selectedProductIds.value.includes(p.product_id))
})

const syncPercent = computed(() => {
  if (syncProgress.value.total <= 0) return 0
  return Math.round((syncProgress.value.current / syncProgress.value.total) * 100)
})

const batchPercent = computed(() => {
  if (batchProgress.value.total <= 0) return 0
  return Math.round((batchProgress.value.current / batchProgress.value.total) * 100)
})

// --- FUNCIONES COMUNES ---
async function refreshAll(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [logo, revs, dStatus] = await Promise.all([
      getGlobalLogo(),
      listImageReviews(),
      getDriveStatus().catch(() => ({ status: 'idle', sync_id: null })),
    ])
    logoInfo.value = logo
    reviewItems.value = revs
    if (dStatus.status === 'processing' || dStatus.status === 'initializing') {
      syncActive.value = true
      syncRunId.value = dStatus.sync_id ?? null
      initDriveWebSocket(dStatus.sync_id ?? undefined)
    }
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    loading.value = false
  }
}

// --- LOGO INSTITUCIONAL ---
async function handleUploadLogo(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.png')) {
    alert('Por favor selecciona un archivo PNG para preservar la transparencia del logo.')
    return
  }
  uploadingLogo.value = true
  error.value = ''
  try {
    await uploadGlobalLogo(file)
    logoInfo.value = await getGlobalLogo()
    cacheTs.value = Date.now()
    successMsg.value = 'Logo institucional actualizado correctamente.'
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    uploadingLogo.value = false
    if (logoInputRef.value) logoInputRef.value.value = ''
  }
}

// --- PREVIEW Y CONTRASTE DE DRIVE ---
async function handlePreviewDrive(): Promise<void> {
  if (!driveFolderId.value.trim()) {
    error.value = 'Por favor ingresa un ID de carpeta válido.'
    return
  }
  previewLoading.value = true
  error.value = ''
  previewData.value = null
  try {
    const result = await previewDriveSync(driveFolderId.value.trim())
    previewData.value = result
    successMsg.value = `Contraste finalizado: ${result.total_files} archivos evaluados.`
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    previewLoading.value = false
  }
}

function resetDriveFolderId(): void {
  driveFolderId.value = DEFAULT_DRIVE_FOLDER_ID
}

// --- SINCRONIZACIÓN DRIVE EN VIVO ---
function initDriveWebSocket(runId?: string): void {
  if (driveWs) {
    try { driveWs.close() }
    catch {}
  }
  try {
    driveWs = openDriveEvents(runId)
    driveWs.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'drive_sync_progress' || payload.status) {
          syncActive.value = true
          syncProgress.value.status = payload.status || 'processing'
          syncProgress.value.current = payload.current ?? syncProgress.value.current
          syncProgress.value.total = payload.total ?? syncProgress.value.total
          syncProgress.value.sku = payload.sku ?? ''
          syncProgress.value.filename = payload.filename ?? ''
          syncProgress.value.message = payload.message ?? ''
          if (payload.stats) {
            syncProgress.value.processed = payload.stats.processed ?? 0
            syncProgress.value.errors = payload.stats.errors ?? 0
            syncProgress.value.no_sku = payload.stats.no_sku ?? 0
          }

          if (payload.status === 'completed' || payload.status === 'failed') {
            syncActive.value = false
            refreshAll()
            if (previewData.value) handlePreviewDrive()
          }
        }
      }
      catch (e) {
        console.warn('Error parseando mensaje WS de Drive:', e)
      }
    }
    driveWs.onerror = () => {
      console.warn('WebSocket de Drive cerrado o con error.')
    }
  }
  catch (e) {
    console.warn('No se pudo abrir WebSocket de Drive:', e)
  }
}

async function handleStartDriveSync(): Promise<void> {
  if (!confirm(`¿Iniciar la sincronización con Google Drive para la carpeta ${driveFolderId.value}?`)) return
  syncStarting.value = true
  error.value = ''
  try {
    const res = await startDriveRun(driveFolderId.value.trim()) as { status: string; sync_id?: string }
    syncRunId.value = res.sync_id ?? null
    syncActive.value = true
    syncProgress.value = {
      status: 'initializing',
      current: 0,
      total: 0,
      sku: '',
      filename: '',
      message: 'Iniciando descarga y contraste...',
      processed: 0,
      errors: 0,
      no_sku: 0,
    }
    initDriveWebSocket(res.sync_id)
    successMsg.value = 'Sincronización iniciada con éxito.'
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    syncStarting.value = false
  }
}

async function handleCancelDriveSync(): Promise<void> {
  if (!syncRunId.value) return
  try {
    await cancelDriveRun(syncRunId.value)
    syncActive.value = false
    successMsg.value = 'Cancelación solicitada.'
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
}

// --- CATÁLOGO Y PROCESAMIENTO MASIVO ---
async function searchCatalog(): Promise<void> {
  productsLoading.value = true
  error.value = ''
  try {
    const res = await listProducts({
      q: productQuery.value.trim(),
      supplier_id: null,
      category_id: null,
      stock: '',
      recent: '',
      type: 'all',
      page: 1,
      page_size: 50,
    })
    products.value = res.items
    selectedProductIds.value = []
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    productsLoading.value = false
  }
}

function toggleSelectAll(): void {
  if (isAllSelected.value) {
    selectedProductIds.value = []
  }
  else {
    selectedProductIds.value = products.value.map(p => p.product_id)
  }
}

async function selectCatalogProduct(product: ProductListItem): Promise<void> {
  selectedSingleProduct.value = product
  singleImagesLoading.value = true
  try {
    singleProductImages.value = await getProductImages(product.product_id)
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    singleImagesLoading.value = false
  }
}

async function processSingleImage(imageId: number, action: 'remove-bg' | 'watermark' | 'logo' | 'webp'): Promise<void> {
  if (!singleProductImages.value) return
  loading.value = true
  try {
    await processProductImage(singleProductImages.value.product_id, imageId, action)
    singleProductImages.value = await getProductImages(singleProductImages.value.product_id)
    cacheTs.value = Date.now()
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    loading.value = false
  }
}

async function setPrimaryImage(imageId: number): Promise<void> {
  if (!singleProductImages.value) return
  loading.value = true
  try {
    await setPrimaryProductImage(singleProductImages.value.product_id, imageId)
    singleProductImages.value = await getProductImages(singleProductImages.value.product_id)
    cacheTs.value = Date.now()
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    loading.value = false
  }
}

// --- PROCESAMIENTO MASIVO POR LOTE ---
async function startBatchProcess(action: 'logo' | 'webp' | 'watermark'): Promise<void> {
  if (!selectedProductIds.value.length) {
    alert('Por favor selecciona al menos un producto.')
    return
  }
  if (action === 'logo' && !logoInfo.value?.exists) {
    alert('No hay un logo institucional configurado. Subí un logo PNG primero en la cabecera.')
    return
  }

  const actionName = action === 'logo' ? 'aplicar el logo institucional a' : action === 'webp' ? 'generar WebP para' : 'aplicar marca de agua a'
  if (!confirm(`¿Deseas ${actionName} los ${selectedProductIds.value.length} productos seleccionados?`)) {
    return
  }

  batchRunning.value = true
  batchAction.value = action
  batchCancelRequested.value = false
  batchProgress.value = {
    current: 0,
    total: selectedProductIds.value.length,
    currentName: '',
    logs: [],
  }

  for (let i = 0; i < selectedProductIds.value.length; i++) {
    if (batchCancelRequested.value) {
      batchProgress.value.logs.unshift('Operación cancelada por el usuario.')
      break
    }
    const pid = selectedProductIds.value[i]
    const prod = products.value.find(p => p.product_id === pid)
    const prodName = prod?.preferred_name || prod?.name || `Producto #${pid}`
    batchProgress.value.current = i + 1
    batchProgress.value.currentName = prodName

    try {
      const pImages = await getProductImages(pid)
      if (!pImages.images.length) {
        batchProgress.value.logs.unshift(`[${prod?.canonical_sku || pid}] Sin imágenes para procesar.`)
        continue
      }

      // Procesar cada imagen del producto
      for (const img of pImages.images) {
        await processProductImage(pid, img.id, action)
      }
      batchProgress.value.logs.unshift(`[${prod?.canonical_sku || pid}] ${action.toUpperCase()} aplicado a ${pImages.images.length} imagen(es).`)
    }
    catch (e) {
      batchProgress.value.logs.unshift(`[${prod?.canonical_sku || pid}] Error: ${getHttpErrorMessage(e)}`)
    }
  }

  cacheTs.value = Date.now()
  successMsg.value = `Procesamiento masivo (${action}) completado.`
}

// --- COLA DE REVISIÓN ---
async function approveReviewItem(item: ImageReview): Promise<void> {
  reviewProcessing.value = item.image_id
  try {
    await approveImage(item.image_id)
    reviewItems.value = await listImageReviews()
    successMsg.value = `Imagen #${item.image_id} aprobada.`
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    reviewProcessing.value = undefined
  }
}

function requestRejectItem(item: ImageReview): void {
  rejectTarget.value = item
  rejectNote.value = ''
  rejectDialog.value = true
}

async function confirmRejectItem(): Promise<void> {
  if (!rejectTarget.value) return
  reviewProcessing.value = rejectTarget.value.image_id
  try {
    await rejectImage(rejectTarget.value.image_id, rejectNote.value)
    rejectDialog.value = false
    reviewItems.value = await listImageReviews()
    successMsg.value = `Imagen #${rejectTarget.value.image_id} rechazada.`
  }
  catch (reason) {
    error.value = getHttpErrorMessage(reason)
  }
  finally {
    reviewProcessing.value = undefined
  }
}

// Helper para formato de bytes
function formatBytes(bytes?: number | null): string {
  if (!bytes) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

onMounted(() => {
  refreshAll()
  searchCatalog()
})

onUnmounted(() => {
  if (driveWs) {
    try { driveWs.close() }
    catch {}
  }
})
</script>

<template>
  <v-container class="py-8" fluid>
    <!-- CABECERA -->
    <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-6">
      <div>
        <h1 class="text-h4 font-weight-bold">Imágenes de productos</h1>
        <p class="text-medium-emphasis mb-0">
          Sincronización con Drive, contraste por SKU canónico, suite de edición masiva y moderación.
        </p>
      </div>

      <!-- LOGO INSTITUCIONAL GLOBAL -->
      <div class="d-flex align-center ga-3 bg-surface pa-2 rounded-lg elevation-1 border">
        <div class="text-right d-none d-sm-block">
          <div class="text-caption font-weight-bold">Logo Institucional</div>
          <div v-if="logoInfo?.exists" class="text-caption text-medium-emphasis">
            {{ logoInfo.width }}×{{ logoInfo.height }} px
          </div>
          <div v-else class="text-caption text-warning">Sin configurar</div>
        </div>

        <div
          class="bg-grey-darken-3 pa-1 rounded d-flex align-center justify-center"
          style="min-width: 48px; height: 36px;"
          :title="logoInfo?.exists ? 'Logo cargado' : 'Sin logo'"
        >
          <v-img
            v-if="logoInfo?.exists"
            :src="`${logoInfo.url}?t=${cacheTs}`"
            height="32"
            width="auto"
            max-width="120"
            contain
          />
          <v-icon v-else color="grey-lighten-1" size="small">mdi-image-off-outline</v-icon>
        </div>

        <input ref="logoInputRef" type="file" accept=".png,image/png" class="d-none" @change="handleUploadLogo" />
        <v-btn
          :loading="uploadingLogo"
          prepend-icon="mdi-upload"
          variant="tonal"
          size="small"
          @click="logoInputRef?.click()"
        >
          {{ logoInfo?.exists ? 'Cambiar' : 'Subir PNG' }}
        </v-btn>

        <v-btn
          icon="mdi-refresh"
          variant="text"
          size="small"
          :loading="loading"
          @click="refreshAll"
        />
      </div>
    </div>

    <!-- ALERTAS -->
    <v-alert v-if="error" class="mb-4" closable type="error" @click:close="error = ''">{{ error }}</v-alert>
    <v-alert v-if="successMsg" class="mb-4" closable type="success" @click:close="successMsg = ''">{{ successMsg }}</v-alert>

    <!-- NAVEGACIÓN ENTRE PESTAÑAS -->
    <v-tabs v-model="activeTab" class="mb-6 border-b" color="primary">
      <v-tab value="drive">
        <v-icon start>mdi-google-drive</v-icon>
        Sincronización con Drive
      </v-tab>
      <v-tab value="catalog">
        <v-icon start>mdi-image-multiple</v-icon>
        Catálogo y Procesamiento Masivo
      </v-tab>
      <v-tab value="reviews">
        <v-icon start>mdi-image-check-outline</v-icon>
        Cola de Revisión
        <v-chip v-if="reviewItems.length" color="warning" size="x-small" class="ml-2 font-weight-bold">
          {{ reviewItems.length }}
        </v-chip>
      </v-tab>
    </v-tabs>

    <!-- CONTENIDO DE PESTAÑAS -->
    <v-window v-model="activeTab">
      <!-- PESTAÑA 1: SINCRONIZACIÓN GOOGLE DRIVE -->
      <v-window-item value="drive">
        <!-- SELECTOR DE CARPETA Y ACCIONES -->
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center ga-2">
            <v-icon color="primary">mdi-folder-google-drive</v-icon>
            Carpeta de Google Drive (Galeria x SKU)
          </v-card-title>
          <v-card-text>
            <p class="text-body-2 text-medium-emphasis mb-4">
              Ingresá el ID de la carpeta de Drive que contiene los archivos de imágenes con el SKU canónico
              (ej: <code>FER_0001_ORG.jpg</code> o imágenes secundarias como <code>FER_0001_ORG - 2.jpg</code>, <code>FER_0001_ORG Dorso.png</code>).
              Admite formatos <strong>HEIC</strong>, <strong>PNG</strong> y <strong>JPG</strong>. Si la imagen ya fue descargada con anterioridad, no se duplicará.
            </p>

            <v-row align="center">
              <v-col cols="12" md="7">
                <v-text-field
                  v-model="driveFolderId"
                  label="ID de Carpeta de Drive"
                  placeholder="13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7"
                  prepend-inner-icon="mdi-folder-key-network"
                  variant="outlined"
                  density="comfortable"
                  hide-details
                >
                  <template #append-inner>
                    <v-btn
                      v-if="driveFolderId !== DEFAULT_DRIVE_FOLDER_ID"
                      variant="text"
                      size="small"
                      @click="resetDriveFolderId"
                    >
                      Restablecer
                    </v-btn>
                  </template>
                </v-text-field>
              </v-col>

              <v-col cols="12" md="5" class="d-flex flex-wrap ga-2">
                <v-btn
                  color="primary"
                  variant="tonal"
                  prepend-icon="mdi-file-find"
                  :loading="previewLoading"
                  @click="handlePreviewDrive"
                >
                  Contrastar archivos
                </v-btn>

                <v-btn
                  color="success"
                  prepend-icon="mdi-sync"
                  :loading="syncStarting || syncActive"
                  @click="handleStartDriveSync"
                >
                  Iniciar sincronización
                </v-btn>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- PANEL DE PROGRESO DE SINCRONIZACIÓN EN VIVO -->
        <v-card v-if="syncActive || syncProgress.status !== 'idle'" class="mb-6 border-primary border">
          <v-card-title class="d-flex align-center justify-space-between bg-primary-lighten-5 py-2">
            <div class="d-flex align-center ga-2">
              <v-progress-circular v-if="syncActive" indeterminate size="20" width="2" color="primary" />
              <v-icon v-else-if="syncProgress.status === 'completed'" color="success">mdi-check-circle</v-icon>
              <v-icon v-else-if="syncProgress.status === 'failed'" color="error">mdi-alert-circle</v-icon>
              <span class="text-subtitle-1 font-weight-bold">
                {{ syncActive ? 'Sincronización en curso' : syncProgress.status === 'completed' ? 'Sincronización completada' : 'Sincronización detenida' }}
              </span>
            </div>

            <v-btn
              v-if="syncActive"
              color="error"
              size="small"
              variant="tonal"
              @click="handleCancelDriveSync"
            >
              Cancelar
            </v-btn>
          </v-card-title>

          <v-card-text class="pt-4">
            <div class="d-flex justify-space-between align-center mb-2">
              <span class="text-body-2 font-weight-medium">
                {{ syncProgress.message || 'Procesando archivos...' }}
              </span>
              <span class="text-caption text-medium-emphasis">
                {{ syncProgress.current }} / {{ syncProgress.total }} ({{ syncPercent }}%)
              </span>
            </div>

            <v-progress-linear
              :model-value="syncPercent"
              color="primary"
              height="10"
              rounded
              striped
              :indeterminate="syncProgress.status === 'initializing'"
            />

            <div v-if="syncProgress.filename" class="text-caption text-medium-emphasis mt-2">
              Archivo actual: <strong>{{ syncProgress.filename }}</strong>
              <span v-if="syncProgress.sku" class="ml-2 font-weight-bold text-primary">[{{ syncProgress.sku }}]</span>
            </div>

            <div class="d-flex ga-4 mt-3">
              <v-chip size="small" color="success" variant="flat">
                Procesadas: {{ syncProgress.processed }}
              </v-chip>
              <v-chip size="small" color="warning" variant="flat">
                Sin SKU: {{ syncProgress.no_sku }}
              </v-chip>
              <v-chip size="small" color="error" variant="flat">
                Errores: {{ syncProgress.errors }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>

        <!-- RESULTADOS DEL CONTRASTE (PREVIEW) -->
        <template v-if="previewData">
          <v-card class="mb-6">
            <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
              <span>Resultado del Contraste con SKU Canónico</span>
              <span class="text-caption text-medium-emphasis">Carpeta: {{ previewData.folder_id }}</span>
            </v-card-title>

            <v-card-text>
              <!-- TARJETAS DE MÉTRICAS -->
              <v-row class="mb-4">
                <v-col cols="6" sm="4" md="2">
                  <v-card variant="tonal" color="primary" class="text-center pa-2">
                    <div class="text-h5 font-weight-bold">{{ previewData.total_files }}</div>
                    <div class="text-caption">Total en Drive</div>
                  </v-card>
                </v-col>
                <v-col cols="6" sm="4" md="2">
                  <v-card variant="tonal" color="success" class="text-center pa-2">
                    <div class="text-h5 font-weight-bold">{{ previewData.matched_count }}</div>
                    <div class="text-caption">Match Principal</div>
                  </v-card>
                </v-col>
                <v-col cols="6" sm="4" md="2">
                  <v-card variant="tonal" color="info" class="text-center pa-2">
                    <div class="text-h5 font-weight-bold">{{ previewData.matches_additional_count }}</div>
                    <div class="text-caption">Match Adicional</div>
                  </v-card>
                </v-col>
                <v-col cols="6" sm="4" md="2">
                  <v-card variant="tonal" color="grey" class="text-center pa-2">
                    <div class="text-h5 font-weight-bold">{{ previewData.already_downloaded_count }}</div>
                    <div class="text-caption">Ya descargadas</div>
                  </v-card>
                </v-col>
                <v-col cols="6" sm="4" md="2">
                  <v-card variant="tonal" color="error" class="text-center pa-2">
                    <div class="text-h5 font-weight-bold">{{ previewData.unmatched_count }}</div>
                    <div class="text-caption">No encontrados</div>
                  </v-card>
                </v-col>
                <v-col cols="6" sm="4" md="2">
                  <v-card variant="tonal" color="warning" class="text-center pa-2">
                    <div class="text-h5 font-weight-bold">{{ previewData.no_sku_count }}</div>
                    <div class="text-caption">Sin SKU</div>
                  </v-card>
                </v-col>
              </v-row>

              <!-- FILTROS DE TABLA -->
              <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
                <v-text-field
                  v-model="previewSearchText"
                  placeholder="Buscar por archivo, SKU o producto..."
                  prepend-inner-icon="mdi-magnify"
                  density="compact"
                  variant="outlined"
                  hide-details
                  style="max-width: 320px;"
                />

                <v-select
                  v-model="previewFilterStatus"
                  :items="[
                    { title: 'Todos los estados', value: 'all' },
                    { title: 'Match Principal', value: 'matched' },
                    { title: 'Ya descargadas', value: 'already_downloaded' },
                    { title: 'No encontrados en Growen', value: 'product_not_found' },
                    { title: 'Sin SKU canónico', value: 'no_sku' }
                  ]"
                  density="compact"
                  variant="outlined"
                  hide-details
                  style="max-width: 250px;"
                />
              </div>

              <!-- TABLA DE ITEMS -->
              <v-table density="comfortable" class="border rounded">
                <thead>
                  <tr>
                    <th>Archivo en Drive</th>
                    <th>SKU Detectado</th>
                    <th>Tipo</th>
                    <th>Producto en Growen</th>
                    <th>Estado de Sincronización</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in previewFilteredItems" :key="item.file_id">
                    <td>
                      <div class="font-weight-medium text-truncate" style="max-width: 240px;" :title="item.filename">
                        {{ item.filename }}
                      </div>
                      <div class="text-caption text-medium-emphasis">
                        {{ formatBytes(item.size_bytes) }} • {{ item.mime_type ? item.mime_type.split('/')[1]?.toUpperCase() : 'ARCHIVO' }}
                      </div>
                    </td>
                    <td>
                      <v-chip v-if="item.sku_extracted" size="small" color="primary" variant="outlined" class="font-weight-bold">
                        {{ item.sku_extracted }}
                      </v-chip>
                      <span v-else class="text-caption text-medium-emphasis">-</span>
                    </td>
                    <td>
                      <v-chip
                        v-if="item.is_additional"
                        size="small"
                        color="info"
                        variant="tonal"
                      >
                        {{ item.additional_label || `Adicional #${item.sort_order + 1}` }}
                      </v-chip>
                      <v-chip
                        v-else-if="item.sku_extracted"
                        size="small"
                        color="success"
                        variant="tonal"
                      >
                        Principal
                      </v-chip>
                      <span v-else class="text-caption text-medium-emphasis">-</span>
                    </td>
                    <td>
                      <template v-if="item.product_id">
                        <router-link
                          :to="`/productos/${item.product_id}/imagenes`"
                          class="text-decoration-none font-weight-medium"
                        >
                          {{ item.product_title || `Producto #${item.product_id}` }}
                        </router-link>
                      </template>
                      <span v-else class="text-caption text-medium-emphasis">-</span>
                    </td>
                    <td>
                      <v-chip
                        v-if="item.match_status === 'matched'"
                        size="small"
                        :color="item.is_additional ? 'info' : 'success'"
                        :prepend-icon="item.is_additional ? 'mdi-image-multiple' : 'mdi-check'"
                      >
                        {{ item.message }}
                      </v-chip>
                      <v-chip
                        v-else-if="item.match_status === 'already_downloaded'"
                        size="small"
                        color="grey"
                        prepend-icon="mdi-cloud-check"
                      >
                        {{ item.message }}
                      </v-chip>
                      <v-chip
                        v-else-if="item.match_status === 'product_not_found'"
                        size="small"
                        color="error"
                        prepend-icon="mdi-close-circle"
                      >
                        {{ item.message }}
                      </v-chip>
                      <v-chip
                        v-else
                        size="small"
                        color="warning"
                        prepend-icon="mdi-help-circle"
                      >
                        {{ item.message }}
                      </v-chip>
                    </td>
                  </tr>
                  <tr v-if="!previewFilteredItems.length">
                    <td colspan="5" class="text-center py-6 text-medium-emphasis">
                      No hay archivos que coincidan con los filtros actuales.
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </v-card-text>
          </v-card>
        </template>
      </v-window-item>

      <!-- PESTAÑA 2: CATÁLOGO Y PROCESAMIENTO MASIVO -->
      <v-window-item value="catalog">
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
            <span>Catálogo de Productos para Edición Masiva</span>
            <div class="d-flex align-center ga-2">
              <v-btn
                color="primary"
                variant="tonal"
                prepend-icon="mdi-tag"
                :disabled="!selectedProductIds.length || batchRunning"
                @click="startBatchProcess('logo')"
              >
                Aplicar Logo Masivo
              </v-btn>
              <v-btn
                color="info"
                variant="tonal"
                prepend-icon="mdi-file-image-outline"
                :disabled="!selectedProductIds.length || batchRunning"
                @click="startBatchProcess('webp')"
              >
                Generar WebP Masivo
              </v-btn>
              <v-btn
                color="secondary"
                variant="tonal"
                prepend-icon="mdi-watermark"
                :disabled="!selectedProductIds.length || batchRunning"
                @click="startBatchProcess('watermark')"
              >
                Marca de Agua Masiva
              </v-btn>
            </div>
          </v-card-title>

          <v-card-text>
            <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
              <v-text-field
                v-model="productQuery"
                placeholder="Buscar por nombre o SKU canónico..."
                prepend-inner-icon="mdi-magnify"
                density="compact"
                variant="outlined"
                hide-details
                style="max-width: 360px;"
                @keyup.enter="searchCatalog"
              >
                <template #append-inner>
                  <v-btn variant="text" size="small" :loading="productsLoading" @click="searchCatalog">
                    Buscar
                  </v-btn>
                </template>
              </v-text-field>

              <div class="d-flex align-center ga-2">
                <v-btn
                  size="small"
                  variant="outlined"
                  @click="toggleSelectAll"
                >
                  {{ isAllSelected ? 'Deseleccionar todos' : 'Seleccionar todos' }}
                </v-btn>
                <v-chip v-if="selectedProductIds.length" color="primary" size="small" class="font-weight-bold">
                  {{ selectedProductIds.length }} seleccionado(s)
                </v-chip>
              </div>
            </div>

            <!-- TABLA DE PRODUCTOS -->
            <v-table density="comfortable" class="border rounded">
              <thead>
                <tr>
                  <th style="width: 48px;">
                    <v-checkbox-btn
                      :model-value="isAllSelected"
                      @click="toggleSelectAll"
                    />
                  </th>
                  <th style="width: 80px;">Portada</th>
                  <th>SKU Canónico</th>
                  <th>Nombre del Producto</th>
                  <th>Imágenes</th>
                  <th class="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="prod in products" :key="prod.product_id">
                  <td>
                    <v-checkbox-btn
                      v-model="selectedProductIds"
                      :value="prod.product_id"
                    />
                  </td>
                  <td>
                    <v-avatar size="48" rounded="sm" color="grey-darken-3">
                      <v-img
                        v-if="prod.image_url"
                        :src="`${prod.image_url}?t=${cacheTs}`"
                        cover
                      />
                      <v-icon v-else color="grey">mdi-image-outline</v-icon>
                    </v-avatar>
                  </td>
                  <td>
                    <v-chip v-if="prod.canonical_sku" size="small" color="primary" class="font-weight-bold">
                      {{ prod.canonical_sku }}
                    </v-chip>
                    <span v-else class="text-caption text-medium-emphasis">Sin SKU</span>
                  </td>
                  <td>
                    <div class="font-weight-medium">{{ prod.preferred_name || prod.name }}</div>
                    <div class="text-caption text-medium-emphasis">ID: #{{ prod.product_id }}</div>
                  </td>
                  <td>
                    <v-chip size="small" :color="prod.images_count > 0 ? 'success' : 'grey'" variant="tonal">
                      {{ prod.images_count }} foto{{ prod.images_count !== 1 ? 's' : '' }}
                    </v-chip>
                  </td>
                  <td class="text-right">
                    <div class="d-flex justify-end ga-2">
                      <v-btn
                        size="small"
                        variant="tonal"
                        color="primary"
                        prepend-icon="mdi-image-edit"
                        :to="`/productos/${prod.product_id}/imagenes`"
                      >
                        Galería y Recorte
                      </v-btn>
                      <v-btn
                        size="small"
                        variant="text"
                        icon="mdi-eye"
                        @click="selectCatalogProduct(prod)"
                      />
                    </div>
                  </td>
                </tr>
                <tr v-if="!products.length && !productsLoading">
                  <td colspan="6" class="text-center py-8 text-medium-emphasis">
                    No se encontraron productos. Intentá buscar por otro término.
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>

        <!-- VISTA RÁPIDA DE IMÁGENES DEL PRODUCTO SELECCIONADO -->
        <v-card v-if="selectedSingleProduct" class="mb-6 border-primary border">
          <v-card-title class="d-flex align-center justify-space-between bg-surface-variant py-2">
            <div>
              <span>Galería rápida: {{ selectedSingleProduct.preferred_name || selectedSingleProduct.name }}</span>
              <v-chip v-if="selectedSingleProduct.canonical_sku" color="primary" size="x-small" class="ml-2">
                {{ selectedSingleProduct.canonical_sku }}
              </v-chip>
            </div>
            <v-btn icon="mdi-close" variant="text" size="small" @click="selectedSingleProduct = null" />
          </v-card-title>

          <v-card-text class="pt-4">
            <div v-if="singleImagesLoading" class="text-center py-6">
              <v-progress-circular indeterminate color="primary" />
            </div>
            <v-row v-else-if="singleProductImages?.images.length">
              <v-col
                v-for="img in singleProductImages.images"
                :key="img.id"
                cols="12"
                sm="6"
                md="4"
                lg="3"
              >
                <v-card variant="outlined" class="h-100 d-flex flex-column">
                  <v-img :src="`${img.display_url || img.url}?t=${cacheTs}`" height="180" cover class="bg-grey-darken-4">
                    <div v-if="img.is_primary" class="position-absolute top-0 left-0 ma-2">
                      <v-chip size="x-small" color="success" class="font-weight-bold">PORTADA</v-chip>
                    </div>
                  </v-img>
                  <v-card-actions class="flex-wrap ga-1 pa-2 mt-auto">
                    <v-btn
                      v-if="!img.is_primary"
                      size="x-small"
                      variant="tonal"
                      color="primary"
                      @click="setPrimaryImage(img.id)"
                    >
                      Hacer Portada
                    </v-btn>
                    <v-btn size="x-small" variant="tonal" @click="processSingleImage(img.id, 'logo')">
                      Logo
                    </v-btn>
                    <v-btn size="x-small" variant="tonal" @click="processSingleImage(img.id, 'webp')">
                      WebP
                    </v-btn>
                    <v-btn size="x-small" variant="tonal" @click="processSingleImage(img.id, 'watermark')">
                      Watermark
                    </v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
            <div v-else class="text-center py-6 text-medium-emphasis">
              Este producto no cuenta con imágenes en la galería.
            </div>
          </v-card-text>
        </v-card>

        <!-- MODAL DE PROCESAMIENTO MASIVO -->
        <v-dialog v-model="batchRunning" persistent max-width="600">
          <v-card title="Procesamiento masivo en lote">
            <v-card-text>
              <div class="mb-3">
                <div class="d-flex justify-space-between text-body-2 font-weight-medium mb-1">
                  <span>Procesando {{ batchProgress.currentName }}</span>
                  <span>{{ batchProgress.current }} / {{ batchProgress.total }} ({{ batchPercent }}%)</span>
                </div>
                <v-progress-linear :model-value="batchPercent" color="primary" height="10" rounded striped />
              </div>

              <div class="text-caption font-weight-bold mb-1">Registro de operaciones:</div>
              <div class="bg-grey-darken-4 pa-3 rounded font-monospace text-caption overflow-y-auto" style="max-height: 180px;">
                <div v-for="(l, idx) in batchProgress.logs" :key="idx">{{ l }}</div>
                <div v-if="!batchProgress.logs.length" class="text-medium-emphasis">Iniciando...</div>
              </div>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn
                v-if="batchProgress.current < batchProgress.total && !batchCancelRequested"
                color="error"
                variant="text"
                @click="batchCancelRequested = true"
              >
                Detener
              </v-btn>
              <v-btn
                v-else
                color="primary"
                @click="batchRunning = false"
              >
                Cerrar
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-window-item>

      <!-- PESTAÑA 3: COLA DE REVISIÓN -->
      <v-window-item value="reviews">
        <v-row v-if="reviewItems.length">
          <v-col v-for="item in reviewItems" :key="item.image_id" cols="12" sm="6" lg="4" xl="3">
            <v-card class="h-100">
              <v-img :src="item.url" cover height="230">
                <template #error>
                  <div class="d-flex h-100 align-center justify-center bg-grey-darken-3">Sin vista previa</div>
                </template>
              </v-img>
              <v-card-title class="text-subtitle-1">Producto #{{ item.product_id }}</v-card-title>
              <v-card-subtitle>Imagen #{{ item.image_id }}</v-card-subtitle>
              <v-card-actions>
                <v-btn color="error" variant="text" @click="requestRejectItem(item)">Rechazar</v-btn>
                <v-spacer />
                <v-btn
                  color="success"
                  :loading="reviewProcessing === item.image_id"
                  variant="tonal"
                  @click="approveReviewItem(item)"
                >
                  Aprobar
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
        <v-card v-else-if="!loading">
          <v-empty-state
            icon="mdi-image-check-outline"
            title="No hay imágenes pendientes de revisión"
            text="Todas las imágenes moderadas han sido revisadas o no hay jobs automáticos pendientes."
          />
        </v-card>
        <v-skeleton-loader v-else type="card, card, card" />

        <!-- DIÁLOGO PARA RECHAZO DE IMAGEN -->
        <v-dialog v-model="rejectDialog" max-width="520">
          <v-card title="Rechazar imagen de producto">
            <v-card-text>
              <v-textarea v-model="rejectNote" label="Motivo del rechazo" rows="3" variant="outlined" />
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn variant="text" @click="rejectDialog = false">Cancelar</v-btn>
              <v-btn
                color="error"
                :loading="reviewProcessing !== undefined"
                @click="confirmRejectItem"
              >
                Rechazar
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-window-item>
    </v-window>
  </v-container>
</template>
