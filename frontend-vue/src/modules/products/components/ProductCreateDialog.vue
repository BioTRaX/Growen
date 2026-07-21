<!-- NG-HEADER: Nombre de archivo: ProductCreateDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductCreateDialog.vue -->
<!-- NG-HEADER: Descripción: Alta operativa de producto y oferta de proveedor en Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import SupplierSelect from '../../suppliers/components/SupplierSelect.vue'
import { getHttpErrorMessage } from '../../../services/http'
import { createProduct, createSupplierItem } from '../api/products'
import { isValidStock, parsePositivePrice } from '../productValidation'
import type { CreatedProduct, ProductCategory } from '../types'
import CategoryCreatableSelect from './CategoryCreatableSelect.vue'
import TagCreatableSelect from './TagCreatableSelect.vue'

const props = defineProps<{ modelValue: boolean; categories: ProductCategory[] }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: [product: CreatedProduct]
  categoryCreated: [category: ProductCategory]
}>()

const title = ref('')
const supplierId = ref<number | null>(null)
const supplierSku = ref('')
const categoryId = ref<number | null>(null)
const subcategoryId = ref<number | null>(null)
const tagNames = ref<string[]>([])
const initialStock = ref(0)
const purchasePrice = ref('')
const salePrice = ref('')
const loading = ref(false)
const error = ref('')
const createdBase = ref<CreatedProduct | null>(null)

const valid = computed(() => Boolean(
  title.value.trim() && supplierId.value && isValidStock(initialStock.value) &&
  parsePositivePrice(purchasePrice.value) && parsePositivePrice(salePrice.value),
))

watch(() => props.modelValue, (open) => {
  if (open) error.value = ''
})

function reset(): void {
  title.value = ''
  supplierId.value = null
  supplierSku.value = ''
  categoryId.value = null
  subcategoryId.value = null
  tagNames.value = []
  initialStock.value = 0
  purchasePrice.value = ''
  salePrice.value = ''
  error.value = ''
  createdBase.value = null
}

function close(): void {
  emit('update:modelValue', false)
  reset()
}

async function submit(): Promise<void> {
  const purchase = parsePositivePrice(purchasePrice.value)
  const sale = parsePositivePrice(salePrice.value)
  if (!valid.value || !supplierId.value || purchase === null || sale === null) return
  loading.value = true
  error.value = ''
  try {
    const product = createdBase.value ?? await createProduct({
      title: title.value.trim(),
      category_id: categoryId.value,
      subcategory_id: subcategoryId.value,
      tag_names: tagNames.value,
      initial_stock: initialStock.value,
    })
    createdBase.value = product
    await createSupplierItem(supplierId.value, {
      supplier_product_id: supplierSku.value.trim() || product.sku_root,
      title: product.title,
      product_id: product.id,
      purchase_price: purchase,
      sale_price: sale,
    })
    emit('created', product)
    close()
  } catch (cause) {
    const message = getHttpErrorMessage(cause, 'No se pudo crear el producto')
    error.value = createdBase.value
      ? `El producto interno #${createdBase.value.id} fue creado, pero falta vincular su oferta: ${message}. Podés corregir proveedor o SKU y reintentar.`
      : message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="760" persistent @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Nuevo producto</v-card-title>
      <v-card-text>
        <v-alert v-if="error" class="mb-4" type="error" variant="tonal">{{ error }}</v-alert>
        <v-alert v-if="createdBase" class="mb-4" type="warning" variant="tonal">
          Producto interno creado. Completá el vínculo de proveedor para que aparezca en el catálogo.
        </v-alert>
        <v-row>
          <v-col cols="12"><v-text-field v-model="title" autofocus :disabled="Boolean(createdBase)" label="Nombre" /></v-col>
          <v-col cols="12"><SupplierSelect v-model="supplierId" label="Proveedor" /></v-col>
          <v-col cols="12" md="6"><v-text-field v-model="supplierSku" label="SKU del proveedor (opcional)" /></v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model.number="initialStock" :disabled="Boolean(createdBase)" label="Stock inicial" min="0" step="1" type="number" />
          </v-col>
          <v-col cols="12" md="6"><v-text-field v-model="purchasePrice" inputmode="decimal" label="Precio de compra" prefix="$" /></v-col>
          <v-col cols="12" md="6"><v-text-field v-model="salePrice" inputmode="decimal" label="Precio de venta" prefix="$" /></v-col>
          <v-col cols="12" md="6">
            <CategoryCreatableSelect
              v-model="categoryId"
              :categories="categories"
              clearable
              :disabled="Boolean(createdBase)"
              kind="category"
              label="Categoría (opcional)"
              @created="emit('categoryCreated', $event)"
            />
          </v-col>
          <v-col cols="12" md="6">
            <CategoryCreatableSelect
              v-model="subcategoryId"
              :categories="categories"
              clearable
              :disabled="Boolean(createdBase)"
              kind="subcategory"
              label="Subcategoría (opcional)"
              @created="emit('categoryCreated', $event)"
            />
          </v-col>
          <v-col cols="12">
            <TagCreatableSelect v-model="tagNames" :disabled="Boolean(createdBase)" />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn :disabled="loading" variant="text" @click="close">Cancelar</v-btn>
        <v-btn color="primary" :disabled="!valid" :loading="loading" @click="submit">
          {{ createdBase ? 'Reintentar vínculo' : 'Crear producto' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
