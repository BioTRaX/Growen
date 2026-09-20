<!-- NG-HEADER: Nombre de archivo: ProductKnowledgeView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/views/ProductKnowledgeView.vue -->
<!-- NG-HEADER: Descripción: Vista detallada del conocimiento canónico asociado a un producto. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import KnowledgeCenterDialog from '../../knowledge/components/KnowledgeCenterDialog.vue'
import { getHttpErrorMessage } from '../../../services/http'
import { getProduct } from '../api/products'
import type { ProductDetail } from '../types'

const route = useRoute()
const productId = Number(route.params.id)
const product = ref<ProductDetail | null>(null)
const loading = ref(false)
const error = ref('')
const productTitle = computed(() => product.value?.preferred_title || product.value?.title || `Producto #${productId}`)

async function load(): Promise<void> {
  if (!Number.isInteger(productId) || productId < 1) {
    error.value = 'Identificador de producto inválido'
    return
  }
  loading.value = true
  error.value = ''
  try {
    product.value = await getProduct(productId)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo cargar el producto')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <v-container class="py-8" fluid>
    <v-btn
      :to="{ name: 'product-detail', params: { id: productId } }"
      prepend-icon="mdi-arrow-left"
      variant="text"
    >
      Volver al producto
    </v-btn>

    <header class="my-5">
      <div class="text-overline text-medium-emphasis">Conocimiento del producto</div>
      <h1 class="text-h4">{{ productTitle }}</h1>
      <p v-if="product?.canonical_sku" class="text-medium-emphasis mb-0">{{ product.canonical_sku }}</p>
    </header>

    <v-progress-linear v-if="loading" class="my-6" color="primary" indeterminate />
    <v-alert v-if="error" class="my-6" type="error" variant="tonal">
      {{ error }}
      <template #append><v-btn size="small" variant="text" @click="load">Reintentar</v-btn></template>
    </v-alert>

    <v-alert
      v-if="product && !product.canonical_product_id"
      class="my-6"
      type="warning"
      variant="tonal"
    >
      Este registro todavía no tiene un producto canónico asociado y no puede administrar conocimiento.
    </v-alert>

    <KnowledgeCenterDialog
      v-if="product?.canonical_product_id"
      :canonical-product-id="product.canonical_product_id"
      embedded
    />
  </v-container>
</template>
