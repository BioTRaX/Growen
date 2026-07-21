<!-- NG-HEADER: Nombre de archivo: PurchaseDetailView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/views/PurchaseDetailView.vue -->
<!-- NG-HEADER: Descripción: Revisión, validación y confirmación de una compra. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { confirmPurchase, getPurchase, getPurchaseImpact, updatePurchase, validatePurchase, type Purchase } from '../../../services/purchases'
import { getHttpErrorMessage } from '../../../services/http'
import { purchaseLineTotal } from '../purchaseLineTotal'
import { validationFeedback } from '../purchaseValidation'

const route = useRoute()
const id = Number(route.params.id)
const purchase = ref<Purchase | null>(null)
const impact = ref<any>(null)
const message = ref('')
const error = ref('')
const busy = ref(false)
const validationBusy = ref(false)
const lineErrors = ref<Record<number, string[]>>({})
const editable = computed(() => ['BORRADOR', 'VALIDADA'].includes(purchase.value?.status ?? ''))
const lineHeaders = [
  { title: 'SKU proveedor', key: 'supplier_sku', width: 128 },
  { title: 'Nombre original', key: 'title', width: 410 },
  { title: 'Cantidad', key: 'qty', width: 104, align: 'end' as const },
  { title: 'Costo bruto', key: 'unit_cost', width: 132, align: 'end' as const },
  { title: 'Bonif. %', key: 'line_discount', width: 104, align: 'end' as const },
  { title: 'Total', key: 'total', width: 152, align: 'end' as const, sortable: false },
  { title: 'Estado', key: 'state', width: 210 },
]

function formatMoney(value: number): string {
  const configuredCurrency = purchase.value?.currency?.toUpperCase() ?? 'ARS'
  const currency = /^[A-Z]{3}$/.test(configuredCurrency) ? configuredCurrency : 'ARS'
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency }).format(value)
}

async function refresh() {
  purchase.value = await getPurchase(id)
  if (purchase.value.status === 'CONFIRMADA' || purchase.value.status === 'ANULADA') impact.value = await getPurchaseImpact(id)
}
async function save() {
  if (!purchase.value) return
  message.value = ''
  error.value = ''
  try {
    await updatePurchase(id, { lines: purchase.value.lines })
    await refresh()
    message.value = 'Cambios guardados.'
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudieron guardar los cambios')
  }
}
async function validate() {
  validationBusy.value = true
  message.value = ''
  error.value = ''
  lineErrors.value = {}
  try {
    const result = await validatePurchase(id)
    lineErrors.value = Object.fromEntries(result.errors.map((issue) => [issue.line_id, issue.errors]))
    const feedback = validationFeedback(result)
    error.value = feedback.error
    message.value = feedback.message
    await refresh()
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo validar la compra')
  } finally {
    validationBusy.value = false
  }
}
async function confirm() {
  message.value = ''
  error.value = ''
  if (purchase.value?.status !== 'VALIDADA') {
    error.value = 'La compra todavía no está validada. Corregí los errores indicados y presioná “Validar” antes de confirmar.'
    return
  }
  busy.value = true
  try {
    const result = await confirmPurchase(id)
    await refresh()
    if (purchase.value) purchase.value.status = 'CONFIRMADA'
    if (!impact.value) impact.value = await getPurchaseImpact(id)
    message.value = `Compra confirmada. ${result.created_products?.length ?? 0} producto(s) creados.`
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo confirmar la compra')
  } finally {
    busy.value = false
  }
}
onMounted(refresh)
</script>

<template>
  <v-container v-if="purchase" fluid class="py-8">
    <div class="d-flex justify-space-between align-center mb-4">
      <div><h1 class="text-h4">Remito {{ purchase.remito_number }}</h1><p>{{ purchase.remito_date }} · {{ purchase.status }}</p></div>
      <div class="d-flex ga-2"><v-btn to="/compras" variant="text">Volver</v-btn><v-btn v-if="editable" @click="save">Guardar</v-btn><v-btn v-if="editable" :loading="validationBusy" color="secondary" @click="validate">Validar</v-btn><v-btn v-if="editable" :disabled="validationBusy" :loading="busy" color="primary" @click="confirm">Confirmar</v-btn></div>
    </div>
    <v-alert v-if="message" class="mb-4" type="success">{{ message }}</v-alert><v-alert v-if="error" class="mb-4" type="error">{{ error }}</v-alert>
    <v-card class="mb-4"><v-card-text class="d-flex ga-6"><span>Total documento: <strong>{{ purchase.documented_total ?? '-' }}</strong></span><span>Total calculado: <strong>{{ purchase.totals?.total ?? '-' }}</strong></span><a v-if="purchase.attachments?.[0]" :href="purchase.attachments[0].url" target="_blank">Ver original</a></v-card-text></v-card>
    <v-data-table class="purchase-lines-table" :headers="lineHeaders" :items="purchase.lines">
      <template #item.supplier_sku="{ item }"><v-text-field v-model="item.supplier_sku" :disabled="!editable" density="compact" hide-details /></template>
      <template #item.title="{ item }"><v-text-field v-model="item.title" :disabled="!editable" density="compact" hide-details /></template>
      <template #item.qty="{ item }"><v-text-field v-model.number="item.qty" :disabled="!editable" type="number" density="compact" hide-details /></template>
      <template #item.unit_cost="{ item }"><v-text-field v-model.number="item.unit_cost" :disabled="!editable" type="number" density="compact" hide-details /></template>
      <template #item.line_discount="{ item }"><v-text-field v-model.number="item.line_discount" :disabled="!editable" :error="Boolean(lineErrors[item.id]?.length)" :title="lineErrors[item.id]?.join('. ')" type="number" density="compact" hide-details /></template>
      <template #item.total="{ item }"><strong class="text-no-wrap">{{ formatMoney(purchaseLineTotal(item)) }}</strong></template>
      <template #item.state="{ value }"><v-chip :color="value === 'OK' ? 'success' : value === 'PENDIENTE_CREACION' ? 'info' : 'error'" size="small">{{ value }}</v-chip></template>
    </v-data-table>
    <v-card v-if="impact" class="mt-6"><v-card-title>Impacto confirmado</v-card-title><v-list><v-list-item v-for="item in impact.items" :key="item.line_id" :title="item.product_name" :subtitle="`Stock ${item.stock} · costo neto $ ${item.net_unit_cost}`"><template #append><v-btn :to="`/productos/${item.product_id}`" size="small" variant="text">Ver producto</v-btn></template></v-list-item></v-list></v-card>
  </v-container>
</template>

<style scoped>
.purchase-lines-table :deep(.v-table__wrapper) {
  overflow-x: auto;
}

.purchase-lines-table :deep(table) {
  min-width: 1240px;
  table-layout: fixed;
}

.purchase-lines-table :deep(th),
.purchase-lines-table :deep(td) {
  padding-inline: 10px !important;
}
</style>
