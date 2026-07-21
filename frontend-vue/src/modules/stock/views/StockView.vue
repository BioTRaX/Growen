<!-- NG-HEADER: Nombre de archivo: StockView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/stock/views/StockView.vue -->
<!-- NG-HEADER: Descripción: Vista principal Vue de existencias, precios y exportaciones. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { listProductCategories, listProductSuppliers } from '../../products/api/products'
import ProductPriceDialog from '../../products/components/ProductPriceDialog.vue'
import ProductStockDialog from '../../products/components/ProductStockDialog.vue'
import type { ProductCategory, ProductListItem, ProductSupplier } from '../../products/types'
import { downloadStockExport, openStockPdf } from '../api/stock'
import StockBuyPriceDialog from '../components/StockBuyPriceDialog.vue'
import StockFilters from '../components/StockFilters.vue'
import StockTable from '../components/StockTable.vue'
import { useStockList } from '../composables/useStockList'

const auth = useAuthStore()
const categories = ref<ProductCategory[]>([]); const suppliers = ref<ProductSupplier[]>([]); const metadataLoading = ref(false)
const stockProduct = ref<ProductListItem | null>(null); const saleProduct = ref<ProductListItem | null>(null); const buyProduct = ref<ProductListItem | null>(null)
const notice = ref(''); const operationError = ref(''); const exportLoading = ref('')
const { items, total, loading, error, filters, totalPages, setFilters, retry } = useStockList()
onMounted(async () => { metadataLoading.value = true; try { [categories.value, suppliers.value] = await Promise.all([listProductCategories('category'), listProductSuppliers()]) } catch (cause) { operationError.value = getHttpErrorMessage(cause) } finally { metadataLoading.value = false } })
function stockSaved(stock: number): void { if (stockProduct.value) items.value = items.value.map(item => item.product_id === stockProduct.value?.product_id ? { ...item, stock } : item); notice.value = 'Stock actualizado' }
function saleSaved(price: number): void { if (saleProduct.value) items.value = items.value.map(item => item.product_id !== saleProduct.value?.product_id ? item : saleProduct.value?.canonical_product_id ? { ...item, canonical_sale_price: price } : { ...item, precio_venta: price }); notice.value = 'Precio de venta actualizado' }
function buySaved(price: number): void { if (buyProduct.value) items.value = items.value.map(item => item.product_id === buyProduct.value?.product_id ? { ...item, precio_compra: price } : item); notice.value = 'Precio de compra actualizado' }
async function exportFile(format: 'xlsx' | 'csv' | 'pdf' | 'tiendanegocio'): Promise<void> { exportLoading.value = format; operationError.value = ''; try { if (format === 'pdf') await openStockPdf(filters.value); else await downloadStockExport(format, filters.value) } catch (cause) { operationError.value = getHttpErrorMessage(cause, 'No se pudo generar la exportación') } finally { exportLoading.value = '' } }
</script>
<template><v-container class="py-8" fluid>
  <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-5"><div><h1 class="text-h4">Stock</h1><p class="text-medium-emphasis">Existencias y precios efectivos del catálogo.</p></div><div class="d-flex flex-wrap ga-2">
    <v-btn v-if="auth.isStaff" to="/compras" prepend-icon="mdi-cart-arrow-down">Compras</v-btn><v-btn v-if="auth.isStaff" to="/stock/shortages" prepend-icon="mdi-alert-minus">Faltantes</v-btn>
    <v-btn :loading="exportLoading === 'xlsx'" @click="exportFile('xlsx')">XLSX</v-btn><v-btn :loading="exportLoading === 'csv'" @click="exportFile('csv')">CSV</v-btn><v-btn :loading="exportLoading === 'pdf'" @click="exportFile('pdf')">PDF</v-btn><v-btn v-if="auth.isStaff" :loading="exportLoading === 'tiendanegocio'" @click="exportFile('tiendanegocio')">TiendaNegocio</v-btn>
  </div></div>
  <v-btn-toggle class="mb-4" color="primary" mandatory :model-value="filters.stock" @update:model-value="setFilters({ stock: $event })"><v-btn value="gt:0">Con stock</v-btn><v-btn value="eq:0">Sin stock</v-btn></v-btn-toggle>
  <StockFilters :categories="categories" :loading="metadataLoading" :model-value="filters" :suppliers="suppliers" @update:model-value="setFilters($event)" />
  <v-alert v-if="error || operationError" class="mb-4" type="error" variant="tonal">{{ error || operationError }}<template #append><v-btn variant="text" @click="retry">Reintentar</v-btn></template></v-alert>
  <v-card><v-card-title>{{ total }} resultado(s)</v-card-title><StockTable :can-edit="auth.isStaff" :items="items" :loading="loading" @edit-buy="buyProduct = $event" @edit-sale="saleProduct = $event" @edit-stock="stockProduct = $event" /><v-divider /><div class="d-flex justify-space-between align-center pa-4"><v-select hide-details density="compact" :items="[25,50,100]" label="Filas" :model-value="filters.page_size" style="max-width:120px" @update:model-value="setFilters({ page_size: Number($event), page: 1 }, false)" /><v-pagination :length="totalPages" :model-value="filters.page" @update:model-value="setFilters({ page: $event }, false)" /></div></v-card>
  <ProductStockDialog :model-value="Boolean(stockProduct)" :product="stockProduct" @saved="stockSaved" @update:model-value="!$event && (stockProduct = null)" />
  <ProductPriceDialog :model-value="Boolean(saleProduct)" :product="saleProduct" @saved="saleSaved" @update:model-value="!$event && (saleProduct = null)" />
  <StockBuyPriceDialog :model-value="Boolean(buyProduct)" :product="buyProduct" @saved="buySaved" @update:model-value="!$event && (buyProduct = null)" />
  <v-snackbar :model-value="Boolean(notice)" color="success" @update:model-value="!$event && (notice = '')">{{ notice }}</v-snackbar>
</v-container></template>
