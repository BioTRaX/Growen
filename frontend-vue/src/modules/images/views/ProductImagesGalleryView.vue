<!-- NG-HEADER: Nombre de archivo: ProductImagesGalleryView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/images/views/ProductImagesGalleryView.vue -->
<!-- NG-HEADER: Descripción: Galería de imágenes de un producto, reemplazo de ProductImagesGallery.tsx -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'

import { getProductImages, deleteProductImage, setPrimaryProductImage, processProductImage, rotateProductImage, cropProductImageSquare, cropProductImageCustom, type ProductImages, type ProductImage } from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'

const route = useRoute()
const router = useRouter()
const productId = computed(() => Number(route.params.id))

const data = ref<ProductImages | null>(null)
const loading = ref(true)
const error = ref('')
const processing = ref<number>()
const cacheTs = ref(Date.now())

const selectedImage = ref<ProductImage | null>(null)
const confirmDeleteId = ref<number | null>(null)
const confirmCropId = ref<number | null>(null)
const cropMargin = ref(0)
const cropMode = ref(false)

const cropperRef = ref<typeof Cropper | null>(null)

async function refresh(): Promise<void> {
  if (!productId.value) return
  loading.value = true
  error.value = ''
  try {
    data.value = await getProductImages(productId.value)
    if (selectedImage.value) {
      const updated = data.value.images.find(i => i.id === selectedImage.value!.id)
      if (updated) selectedImage.value = updated
      else selectedImage.value = null
    }
  }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { loading.value = false }
}

function addCacheBuster(url: string | null | undefined): string {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}t=${cacheTs.value}`
}

async function handleAction(action: () => Promise<void>, imageId?: number) {
  if (imageId !== undefined) processing.value = imageId
  try {
    await action()
    await refresh()
  } catch (reason) {
    alert(getHttpErrorMessage(reason) || 'Error en la operación')
  } finally {
    if (imageId !== undefined) processing.value = undefined
  }
}

async function setPrimary(imgId: number) { await handleAction(() => setPrimaryProductImage(productId.value, imgId), imgId) }
async function removeImage(imgId: number) { await handleAction(async () => { await deleteProductImage(productId.value, imgId); selectedImage.value = null; confirmDeleteId.value = null }, imgId) }
async function rotateImage(imgId: number, degrees: number) { await handleAction(async () => { await rotateProductImage(productId.value, imgId, degrees); cacheTs.value = Date.now() }, imgId) }
async function processImage(imgId: number, action: 'webp' | 'watermark' | 'logo' | 'remove-bg') { await handleAction(async () => { await processProductImage(productId.value, imgId, action); if (action !== 'remove-bg') cacheTs.value = Date.now() }, imgId) }
async function cropSquare(imgId: number) { await handleAction(async () => { await cropProductImageSquare(productId.value, imgId, cropMargin.value); cacheTs.value = Date.now(); confirmCropId.value = null }, imgId) }

function cancelCrop() {
  cropMode.value = false
}

async function applyCustomCrop() {
  if (!cropperRef.value || !selectedImage.value) return
  const result = cropperRef.value.getResult()
  if (!result || !result.coordinates || !result.imageSize) {
    alert('Error al obtener coordenadas de recorte')
    return
  }

  // Calculate percentages
  const { width, height } = result.imageSize
  const { left, top, width: cropWidth, height: cropHeight } = result.coordinates

  const cropData = {
    x: (left / width) * 100,
    y: (top / height) * 100,
    width: (cropWidth / width) * 100,
    height: (cropHeight / height) * 100
  }

  await handleAction(async () => {
    await cropProductImageCustom(productId.value, selectedImage.value!.id, cropData)
    cacheTs.value = Date.now()
    cropMode.value = false
  }, selectedImage.value.id)
}

async function downloadImage(img: ProductImage) {
  try {
    const downloadUrl = img.display_url || img.url
    if (!downloadUrl) return
    const response = await fetch(downloadUrl)
    const blob = await response.blob()

    let ext = 'webp'
    if (downloadUrl.includes('.webp')) ext = 'webp'
    else if (downloadUrl.includes('.jpg') || downloadUrl.includes('.jpeg')) ext = 'jpg'
    else if (downloadUrl.includes('.png')) ext = 'png'

    let baseName = 'image'
    if (data.value?.canonical_sku && data.value.canonical_sku.trim()) {
      baseName = data.value.canonical_sku.trim()
    } else if (data.value?.product_name && data.value.product_name.trim()) {
      baseName = data.value.product_name.trim().replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 50)
    } else {
      baseName = `image-${img.id}`
    }

    const filename = `${baseName}.${ext}`
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)
  } catch (e) {
    console.error('Download error:', e)
    alert('Error al descargar imagen')
  }
}

onMounted(refresh)
</script>

<template>
  <v-container class="py-8" fluid>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" class="mb-4" to="/imagenes-productos">Volver</v-btn>

    <div v-if="loading" class="d-flex align-center justify-center pa-12">
      <v-progress-circular indeterminate color="primary" size="64" />
    </div>
    <v-alert v-else-if="error" type="error" closable @click:close="error = ''">{{ error }}</v-alert>
    <template v-else-if="data">
      <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-6">
        <div>
          <h1 class="text-h4 mb-1">{{ data.product_name }}</h1>
          <div class="d-flex align-center ga-2">
            <v-chip v-if="data.canonical_sku" color="success" size="small" class="font-weight-bold">{{ data.canonical_sku }}</v-chip>
            <span class="text-medium-emphasis">{{ data.total }} imagen{{ data.total !== 1 ? 'es' : '' }}</span>
          </div>
        </div>
        <v-btn prepend-icon="mdi-refresh" variant="tonal" @click="refresh">Actualizar</v-btn>
      </div>

      <v-card v-if="data.images.length === 0" class="pa-12 text-center text-medium-emphasis">
        <v-icon size="64" class="mb-4">mdi-image-off-outline</v-icon>
        <p>Este producto no tiene imágenes</p>
      </v-card>

      <v-row v-else>
        <v-col v-for="img in data.images" :key="img.id" cols="12" sm="6" md="4" lg="3" xl="2">
          <v-card @click="selectedImage = img" hover :border="img.is_primary ? 'success' : undefined">
            <v-img :src="addCacheBuster(img.display_url ?? img.url)" cover aspect-ratio="1" class="bg-grey-darken-4">
              <template #placeholder>
                <div class="d-flex align-center justify-center fill-height">
                  <v-progress-circular indeterminate color="grey-lighten-4" />
                </div>
              </template>
              <div v-if="img.is_primary" class="position-absolute top-0 left-0 ma-2">
                <v-chip size="x-small" color="success" class="font-weight-bold">PRINCIPAL</v-chip>
              </div>
              <div v-if="img.has_webp" class="position-absolute top-0 right-0 ma-2">
                <v-chip size="x-small" color="primary" class="font-weight-bold">WebP</v-chip>
              </div>
            </v-img>
            <div class="d-flex justify-space-between px-3 py-2 text-caption bg-grey-darken-3">
              <span>{{ img.size_human }}</span>
              <span v-if="img.width && img.height">{{ img.width }}×{{ img.height }}</span>
            </div>
          </v-card>
        </v-col>
      </v-row>

      <v-dialog :model-value="!!selectedImage" max-width="1000" scrollable @update:model-value="(v) => { if (!v) selectedImage = null }">
        <v-card v-if="selectedImage" height="90vh">
          <v-toolbar color="surface" density="compact">
            <v-toolbar-title>Imagen #{{ selectedImage.id }}</v-toolbar-title>
            <v-spacer />
            <v-btn icon="mdi-close" variant="text" @click="selectedImage = null" />
          </v-toolbar>

          <v-card-text class="pa-0 d-flex flex-column flex-md-row h-100 overflow-hidden">
            <!-- Image Area -->
            <div class="flex-grow-1 bg-grey-darken-4 d-flex flex-column position-relative h-100 overflow-auto" style="min-width: 0;">
              <div class="flex-grow-1 d-flex align-center justify-center pa-4">
                <template v-if="cropMode">
                  <Cropper
                    ref="cropperRef"
                    class="w-100 h-100"
                    :src="addCacheBuster(selectedImage.display_url ?? selectedImage.url)"
                    :stencil-props="{ aspectRatio: 0 }"
                    background-class="bg-grey-darken-4"
                  />
                </template>
                <v-img
                  v-else
                  :src="addCacheBuster(selectedImage.display_url ?? selectedImage.url)"
                  contain
                  max-height="100%"
                  class="w-100 h-100"
                />
              </div>

              <div v-if="cropMode" class="bg-surface pa-3 d-flex justify-center ga-3 elevation-4 position-absolute bottom-0 w-100">
                <v-btn variant="text" :disabled="processing === selectedImage.id" @click="cancelCrop">Cancelar</v-btn>
                <v-btn color="primary" :loading="processing === selectedImage.id" prepend-icon="mdi-check" @click="applyCustomCrop">Aplicar Recorte</v-btn>
              </div>
            </div>

            <!-- Sidebar -->
            <v-divider vertical class="d-none d-md-block" />
            <v-divider class="d-md-none" />

            <div class="pa-4 bg-surface h-100 overflow-y-auto" style="width: 320px; flex-shrink: 0;">
              <div class="text-subtitle-1 font-weight-bold mb-2">Metadatos</div>
              <v-table density="compact" class="text-caption mb-4 bg-transparent">
                <tbody>
                  <tr><td class="text-medium-emphasis">ID</td><td>{{ selectedImage.id }}</td></tr>
                  <tr><td class="text-medium-emphasis">Formato</td><td>{{ selectedImage.mime || '?' }}</td></tr>
                  <tr><td class="text-medium-emphasis">Dimensiones</td><td>{{ selectedImage.width || '?' }} × {{ selectedImage.height || '?' }} px</td></tr>
                  <tr><td class="text-medium-emphasis">Tamaño</td><td>{{ selectedImage.size_human }}</td></tr>
                  <tr><td class="text-medium-emphasis">Creación</td><td>{{ selectedImage.created_at ? new Date(selectedImage.created_at).toLocaleDateString() : '?' }}</td></tr>
                  <tr v-if="selectedImage.checksum_sha256">
                    <td class="text-medium-emphasis">SHA256</td>
                    <td class="text-truncate" style="max-width: 120px;" :title="selectedImage.checksum_sha256">{{ selectedImage.checksum_sha256.substring(0, 16) }}...</td>
                  </tr>
                </tbody>
              </v-table>

              <template v-if="Object.keys((selectedImage as any).versions || {}).length">
                <div class="text-subtitle-2 font-weight-bold mb-2">Versiones</div>
                <v-list density="compact" class="bg-transparent mb-4">
                  <v-list-item v-for="(v, kind) in ((selectedImage as any).versions || {})" :key="kind" class="px-0 py-1 min-h-0">
                    <div class="d-flex justify-space-between w-100 text-caption">
                      <span class="font-weight-bold text-uppercase">{{ kind }}</span>
                      <span>{{ v.width }}×{{ v.height }} • {{ v.size_human }}</span>
                    </div>
                  </v-list-item>
                </v-list>
              </template>

              <div class="text-subtitle-1 font-weight-bold mb-2 mt-4">Procesamiento</div>
              <div class="d-flex flex-column ga-2 mb-4">
                <div class="d-flex ga-2">
                  <v-btn class="flex-grow-1" size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" @click="rotateImage(selectedImage.id, 270)">↺ -90°</v-btn>
                  <v-btn class="flex-grow-1" size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" @click="rotateImage(selectedImage.id, 90)">↻ +90°</v-btn>
                </div>

                <div class="d-flex ga-2">
                  <v-btn class="flex-grow-1" size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" @click="cropMode = true" prepend-icon="mdi-crop">Recortar</v-btn>
                  <template v-if="confirmCropId === selectedImage.id">
                    <div class="d-flex flex-column ga-2 flex-grow-1 pa-2 border rounded">
                      <div class="d-flex align-center ga-2">
                        <span class="text-caption text-nowrap">M: {{ cropMargin }}%</span>
                        <v-slider v-model="cropMargin" min="0" max="40" step="5" hide-details density="compact" />
                      </div>
                      <div class="d-flex ga-2">
                        <v-btn class="flex-grow-1" color="primary" size="small" :loading="processing === selectedImage.id" @click="cropSquare(selectedImage.id)">Aplicar</v-btn>
                        <v-btn size="small" icon="mdi-close" variant="text" @click="confirmCropId = null" />
                      </div>
                    </div>
                  </template>
                  <v-btn v-else class="flex-grow-1" size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" @click="confirmCropId = selectedImage.id" prepend-icon="mdi-crop-square">Cuadrado</v-btn>
                </div>

                <v-btn size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" prepend-icon="mdi-file-image-outline" @click="processImage(selectedImage.id, 'webp')">Generar WebP</v-btn>
                <v-btn size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" prepend-icon="mdi-watermark" @click="processImage(selectedImage.id, 'watermark')">Marca de Agua</v-btn>
                <v-btn size="small" variant="tonal" :disabled="processing === selectedImage.id || cropMode" prepend-icon="mdi-tag" @click="processImage(selectedImage.id, 'logo')">Aplicar Logo</v-btn>
              </div>

              <div class="text-subtitle-1 font-weight-bold mb-2 mt-4">Acciones</div>
              <div class="d-flex flex-column ga-2">
                <v-btn v-if="!selectedImage.is_primary" size="small" color="primary" variant="tonal" :disabled="processing === selectedImage.id || cropMode" prepend-icon="mdi-star" @click="setPrimary(selectedImage.id)">Establecer Principal</v-btn>
                <v-btn size="small" variant="tonal" :disabled="cropMode" prepend-icon="mdi-download" @click="downloadImage(selectedImage)">Descargar</v-btn>

                <template v-if="confirmDeleteId === selectedImage.id">
                  <div class="d-flex ga-2 mt-2">
                    <v-btn class="flex-grow-1" color="error" size="small" :loading="processing === selectedImage.id" @click="removeImage(selectedImage.id)">Confirmar</v-btn>
                    <v-btn class="flex-grow-1" size="small" @click="confirmDeleteId = null">Cancelar</v-btn>
                  </div>
                </template>
                <v-btn v-else size="small" color="error" variant="text" :disabled="processing === selectedImage.id || cropMode || selectedImage.locked" prepend-icon="mdi-delete" @click="confirmDeleteId = selectedImage.id">Eliminar</v-btn>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-dialog>
    </template>
  </v-container>
</template>
