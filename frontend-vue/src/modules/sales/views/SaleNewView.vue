<!-- NG-HEADER: Nombre de archivo: SaleNewView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/sales/views/SaleNewView.vue -->
<!-- NG-HEADER: Descripción: POS Vue con cotización autoritativa y guardado idempotente. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { createCustomer, searchCustomers, type Customer } from '../../../services/customers'
import { createSale, listChannels, quoteSale, searchProducts, uploadAttachment, type SaleDraft, type SaleLine } from '../../../services/sales'
import { getHttpErrorMessage } from '../../../services/http'

const router = useRouter(); const customers = ref<Customer[]>([]); const customer = ref<Customer | null>(null); const customerSearch = ref('')
const products = ref<any[]>([]); const productSearch = ref(''); const items = ref<SaleLine[]>([]); const channels = ref<any[]>([]); const channelId = ref<number | null>(null)
const saleKind = ref('MOSTRADOR'); const note = ref(''); const costConcept = ref(''); const costAmount = ref<number | null>(null); const costs = ref<any[]>([])
const quote = ref<any>({ total_amount: 0 }); const files = ref<File[]>([]); const error = ref(''); const saving = ref(false); const dirty = ref(false)
const quickDialog = ref(false); const quickName = ref(''); const quickDocument = ref(''); let timer: ReturnType<typeof setTimeout> | undefined

listChannels().then(value => { channels.value = value })
watch(customerSearch, value => { clearTimeout(timer); if (value?.length >= 2) timer = setTimeout(() => searchCustomers(value).then(result => { customers.value = result }), 250) })
watch(productSearch, value => { clearTimeout(timer); if (value?.length >= 2) timer = setTimeout(() => searchProducts(value).then(result => { products.value = result }), 250) })
watch([items, costs, channelId, saleKind, note], async () => { dirty.value = true; try { quote.value = await quoteSale({ items: items.value, additional_costs: costs.value }) } catch { /* el guardado mostrará el error autoritativo */ } }, { deep: true })
function addProduct(product: any) { const current = items.value.find(item => item.product_id === product.product_id); if (current) current.qty += 1; else items.value.push({ product_id: product.product_id, product_name: product.title, qty: 1, unit_price: product.price || 0, line_discount: 0 }); productSearch.value = '' }
function addCost() { if (costConcept.value && costAmount.value) { costs.value.push({ concept: costConcept.value, amount: costAmount.value }); costConcept.value = ''; costAmount.value = null } }
async function quickCreate() { try { const result = await createCustomer({ name: quickName.value, document_type: quickDocument.value ? 'DNI' : undefined, document_number: quickDocument.value || undefined }); customer.value = { id: result.id, name: quickName.value, is_active: true }; customers.value = [customer.value]; quickDialog.value = false } catch (exception) { error.value = getHttpErrorMessage(exception) } }
async function save() {
  saving.value = true; error.value = ''
  try {
    const payload: SaleDraft = { customer: customer.value ? { id: customer.value.id } : undefined, items: items.value, sale_kind: saleKind.value, channel_id: channelId.value || undefined, note: note.value || undefined, additional_costs: costs.value }
    const result = await createSale(payload, crypto.randomUUID()); let failed = 0
    for (const file of files.value) { try { await uploadAttachment(result.sale_id, file) } catch { failed += 1 } }
    dirty.value = false; await router.push({ path: `/ventas/${result.sale_id}`, query: failed ? { attachments_failed: String(failed) } : {} })
  } catch (exception) { error.value = getHttpErrorMessage(exception) } finally { saving.value = false }
}
onBeforeRouteLeave(() => !dirty.value || confirm('Hay cambios sin guardar. ¿Salir?')); onBeforeUnmount(() => clearTimeout(timer))
</script>

<template><v-container fluid class="py-8"><v-btn to="/ventas" variant="text">Volver</v-btn><h1 class="text-h4 mb-6">Nueva venta</h1><v-alert v-if="error" type="error" class="mb-4">{{error}}</v-alert><v-row><v-col cols="12" lg="8"><v-card><v-card-text><v-row><v-col><v-autocomplete v-model="customer" v-model:search="customerSearch" :items="customers" item-title="name" return-object label="Cliente (vacío = Consumidor Final)"/><v-btn size="small" variant="text" @click="quickDialog=true">Alta rápida</v-btn></v-col><v-col><v-select v-model="saleKind" :items="['MOSTRADOR','PEDIDO']" label="Tipo"/></v-col><v-col><v-select v-model="channelId" :items="channels" item-title="name" item-value="id" label="Canal" clearable/></v-col></v-row><v-autocomplete v-model:search="productSearch" :items="products" item-title="title" return-object label="Buscar producto, SKU o código" @update:model-value="product=>product&&addProduct(product)"/>
<v-table><thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Desc.</th><th></th></tr></thead><tbody><tr v-for="(line,index) in items" :key="line.product_id"><td>{{line.product_name}}</td><td><v-text-field v-model.number="line.qty" type="number" min="0.01" step="0.01" hide-details/></td><td><v-text-field v-model.number="line.unit_price" type="number" step="0.01" hide-details/></td><td><v-text-field v-model.number="line.line_discount" type="number" min="0" max="100" hide-details/></td><td><v-btn icon="mdi-delete" variant="text" @click="items.splice(index,1)"/></td></tr></tbody></v-table><v-textarea v-model="note" label="Nota"/><v-file-input v-model="files" multiple label="Adjuntos preparados" accept="application/pdf,image/jpeg,image/png,image/webp"/></v-card-text></v-card></v-col>
<v-col cols="12" lg="4"><v-card><v-card-title>Costos adicionales</v-card-title><v-card-text><div class="d-flex ga-2"><v-text-field v-model="costConcept" label="Concepto"/><v-text-field v-model.number="costAmount" type="number" label="Monto"/></div><v-btn @click="addCost">Agregar</v-btn><v-list><v-list-item v-for="(cost,index) in costs" :key="index" :title="cost.concept" :append-title="`$ ${cost.amount}`"/></v-list><v-divider/><div class="text-h5 mt-4">Total $ {{quote.total_amount||0}}</div><v-btn block color="primary" class="mt-4" :loading="saving" :disabled="!items.length" @click="save">Guardar borrador</v-btn></v-card-text></v-card></v-col></v-row>
<v-dialog v-model="quickDialog" max-width="520"><v-card><v-card-title>Alta rápida de cliente</v-card-title><v-card-text><v-text-field v-model="quickName" label="Nombre"/><v-text-field v-model="quickDocument" label="DNI (opcional)"/></v-card-text><v-card-actions><v-spacer/><v-btn @click="quickDialog=false">Cancelar</v-btn><v-btn color="primary" :disabled="!quickName.trim()" @click="quickCreate">Crear y seleccionar</v-btn></v-card-actions></v-card></v-dialog>
</v-container></template>
