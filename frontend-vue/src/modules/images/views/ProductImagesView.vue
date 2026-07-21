<!-- NG-HEADER: Nombre de archivo: ProductImagesView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/images/views/ProductImagesView.vue -->
<!-- NG-HEADER: Descripción: Cola de revisión y procesamiento de imágenes para staff. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getProductImages, approveImage, listImageReviews, processProductImage, rejectImage, setPrimaryProductImage, type ImageReview, type ProductImages } from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'
import { listProducts } from '../../products/api/products'
import type { ProductListItem } from '../../products/types'

const items = ref<ImageReview[]>([])
const loading = ref(false)
const processing = ref<number>()
const error = ref('')
const rejectDialog = ref(false)
const rejectTarget = ref<ImageReview>()
const rejectNote = ref('')
const productQuery = ref('')
const products = ref<ProductListItem[]>([])
const productImages = ref<ProductImages>()
const selectedImageIds = ref<number[]>([])

async function refresh(): Promise<void> {
  loading.value = true
  error.value = ''
  try { items.value = await listImageReviews() }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { loading.value = false }
}

async function approve(item: ImageReview): Promise<void> {
  processing.value = item.image_id
  try { await approveImage(item.image_id); await refresh() }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { processing.value = undefined }
}

function requestReject(item: ImageReview): void {
  rejectTarget.value = item
  rejectNote.value = ''
  rejectDialog.value = true
}

async function confirmReject(): Promise<void> {
  if (!rejectTarget.value) return
  processing.value = rejectTarget.value.image_id
  try {
    await rejectImage(rejectTarget.value.image_id, rejectNote.value)
    rejectDialog.value = false
    await refresh()
  } catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { processing.value = undefined }
}
async function searchProducts(): Promise<void> { try { products.value = (await listProducts({ q: productQuery.value, supplier_id: null, category_id: null, stock: '', recent: '', type: 'all', page: 1, page_size: 20 })).items } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function selectProduct(product: ProductListItem): Promise<void> { try { productImages.value = await getProductImages(product.product_id); selectedImageIds.value = [] } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function processOne(imageId: number, action: 'remove-bg' | 'watermark' | 'logo' | 'webp'): Promise<void> { if (!productImages.value) return; processing.value = imageId; try { await processProductImage(productImages.value.product_id, imageId, action); productImages.value = await getProductImages(productImages.value.product_id) } catch (reason) { error.value = getHttpErrorMessage(reason) } finally { processing.value = undefined } }
async function processSelected(): Promise<void> { for (const imageId of selectedImageIds.value) await processOne(imageId, 'webp') }
async function setPrimary(imageId: number): Promise<void> { if (!productImages.value) return; await setPrimaryProductImage(productImages.value.product_id, imageId); productImages.value = await getProductImages(productImages.value.product_id) }

onMounted(refresh)
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-6">
      <div>
        <h1 class="text-h4">Imágenes de productos</h1>
        <p class="text-medium-emphasis mb-0">Revisión de imágenes encontradas y procesadas.</p>
      </div>
      <v-btn prepend-icon="mdi-refresh" :loading="loading" variant="tonal" @click="refresh">Actualizar</v-btn>
    </div>
    <v-alert v-if="error" class="mb-4" closable type="error" @click:close="error = ''">{{ error }}</v-alert>
    <v-row v-if="items.length">
      <v-col v-for="item in items" :key="item.image_id" cols="12" sm="6" lg="4" xl="3">
        <v-card class="h-100">
          <v-img :src="item.url" cover height="230"><template #error><div class="d-flex h-100 align-center justify-center">Sin vista previa</div></template></v-img>
          <v-card-title class="text-subtitle-1">Producto #{{ item.product_id }}</v-card-title>
          <v-card-subtitle>Imagen #{{ item.image_id }}</v-card-subtitle>
          <v-card-actions>
            <v-btn color="error" variant="text" @click="requestReject(item)">Rechazar</v-btn>
            <v-spacer />
            <v-btn color="success" :loading="processing === item.image_id" variant="tonal" @click="approve(item)">Aprobar</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
    <v-card v-else-if="!loading"><v-empty-state icon="mdi-image-check-outline" title="No hay imágenes pendientes" /></v-card>
    <v-skeleton-loader v-else type="card, card, card" />

    <v-dialog v-model="rejectDialog" max-width="520">
      <v-card title="Rechazar imagen">
        <v-card-text><v-textarea v-model="rejectNote" label="Motivo" rows="3" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="rejectDialog = false">Cancelar</v-btn><v-btn color="error" :loading="processing !== undefined" @click="confirmReject">Rechazar</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-card class="mt-8"><v-card-title>Selector y procesamiento</v-card-title><v-card-text><v-text-field v-model="productQuery" label="Buscar producto" append-inner-icon="mdi-magnify" @click:append-inner="searchProducts" @keyup.enter="searchProducts" /><v-list v-if="products.length" density="compact" max-height="240" class="overflow-y-auto"><v-list-item v-for="product in products" :key="product.product_id" :title="product.preferred_name ?? product.name" :subtitle="product.canonical_sku ?? ''" @click="selectProduct(product)" /></v-list></v-card-text><template v-if="productImages"><v-divider/><v-card-item :title="productImages.product_name" :subtitle="productImages.canonical_sku ?? ''"><template #append><v-btn :disabled="!selectedImageIds.length" @click="processSelected">Generar WebP seleccionadas</v-btn></template></v-card-item><v-row class="pa-4"><v-col v-for="image in productImages.images" :key="image.id" cols="12" sm="6" lg="4"><v-card><v-img :src="image.display_url ?? image.url ?? ''" height="180" cover/><v-card-text><v-checkbox-btn v-model="selectedImageIds" :value="image.id" label="Seleccionar"/><v-chip v-if="image.is_primary" size="small" color="primary">Portada</v-chip><v-chip v-if="image.has_webp" size="small" color="success">WebP</v-chip></v-card-text><v-card-actions class="flex-wrap"><v-btn size="small" variant="text" @click="setPrimary(image.id)">Portada</v-btn><v-btn size="small" variant="text" @click="processOne(image.id, 'webp')">WebP</v-btn><v-btn size="small" variant="text" @click="processOne(image.id, 'remove-bg')">Quitar fondo</v-btn><v-btn size="small" variant="text" @click="processOne(image.id, 'watermark')">Watermark</v-btn><v-btn size="small" variant="text" @click="processOne(image.id, 'logo')">Logo</v-btn></v-card-actions></v-card></v-col></v-row></template></v-card>
  </v-container>
</template>
