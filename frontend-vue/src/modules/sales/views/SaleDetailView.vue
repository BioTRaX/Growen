<!-- NG-HEADER: Nombre de archivo: SaleDetailView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/sales/views/SaleDetailView.vue -->
<!-- NG-HEADER: Descripción: Detalle, edición de borrador y ciclo operativo de una venta. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  addPayment, annulSale, confirmSale, createReturn, deleteAttachment, deliverSale, getSale,
  getTimeline, releaseReservation, reserveSale, updateSaleLines, uploadAttachment, type Sale,
} from '../../../services/sales'
import { getHttpErrorMessage } from '../../../services/http'

const route = useRoute(); const id = Number(route.params.id)
const sale = ref<Sale | null>(null); const timeline = ref<any[]>([]); const error = ref(''); const notice = ref('')
const loading = ref(false); const reason = ref(''); const paymentAmount = ref<number | null>(null); const paymentMethod = ref('efectivo')
const returnLineId = ref<number | null>(null); const returnQty = ref<number | null>(null); const returnReason = ref('')
const files = ref<File[]>([]); const draftQty = ref<Record<number, number>>({})

async function load() {
  loading.value = true; error.value = ''
  try {
    const [detail, events] = await Promise.all([getSale(id), getTimeline(id)])
    sale.value = detail; timeline.value = events
    for (const line of detail.lines ?? []) if (line.id) draftQty.value[line.id] = line.qty
    if (route.query.attachments_failed) notice.value = `${route.query.attachments_failed} adjunto(s) requieren reintento.`
  } catch (exception) { error.value = getHttpErrorMessage(exception) } finally { loading.value = false }
}
async function action(fn: () => Promise<any>, message = '') { try { error.value = ''; await fn(); if (message) notice.value = message; await load() } catch (exception) { error.value = getHttpErrorMessage(exception) } }
async function saveLine(lineId: number) { await action(() => updateSaleLines(id, [{ op: 'update', line_id: lineId, qty: draftQty.value[lineId] }]), 'Línea actualizada') }
async function removeLine(lineId: number) { await action(() => updateSaleLines(id, [{ op: 'remove', line_id: lineId }]), 'Línea eliminada') }
async function returnItem() { if (!returnLineId.value || !returnQty.value) return; await action(() => createReturn(id, { reason: returnReason.value, items: [{ sale_line_id: returnLineId.value, qty: returnQty.value }] }), 'Devolución registrada') }
async function uploadFiles() { const pending = [...files.value]; files.value = []; for (const file of pending) await action(() => uploadAttachment(id, file), `${file.name} adjuntado`) }
onMounted(load)
</script>

<template><v-container fluid class="py-8">
  <div class="d-flex justify-space-between"><v-btn to="/ventas" variant="text" prepend-icon="mdi-arrow-left">Ventas</v-btn><v-btn :href="`/sales/${id}/receipt`" target="_blank" prepend-icon="mdi-printer">Recibo</v-btn></div>
  <v-alert v-if="error" type="error" class="my-4">{{ error }}</v-alert><v-alert v-if="notice" type="info" closable class="my-4" @click:close="notice=''">{{ notice }}</v-alert>
  <v-card v-if="sale"><v-card-title class="d-flex justify-space-between"><span>Venta #{{ sale.id }} · {{ sale.customer_name || 'Consumidor Final' }}</span><v-chip>{{ sale.status }}</v-chip></v-card-title><v-card-subtitle>{{ sale.channel_name || 'Sin canal' }} · {{ sale.payment_status }}</v-card-subtitle>
  <v-card-text><v-data-table :items="sale.lines" :headers="[{title:'Producto',key:'product_name'},{title:'SKU',key:'sku'},{title:'Cantidad',key:'qty'},{title:'Precio',key:'unit_price'},{title:'Total',key:'total'},{title:'',key:'actions'}]">
    <template #item.qty="{item}"><v-text-field v-if="sale?.allowed_actions?.edit && item.id" v-model.number="draftQty[item.id]" type="number" min="0.01" step="0.01" density="compact" hide-details/><span v-else>{{item.qty}}</span></template>
    <template #item.actions="{item}"><div v-if="sale?.allowed_actions?.edit && item.id"><v-btn size="small" variant="text" @click="saveLine(item.id)">Guardar</v-btn><v-btn size="small" variant="text" color="error" @click="removeLine(item.id)">Quitar</v-btn></div></template>
  </v-data-table>
  <div class="d-flex justify-end"><v-list width="360"><v-list-item title="Subtotal" :append-title="`$ ${sale.subtotal}`"/><v-list-item title="Descuento" :append-title="`$ ${sale.discount_amount}`"/><v-list-item title="Extras" :append-title="`$ ${sale.additional_cost_total}`"/><v-list-item title="Total" :append-title="`$ ${sale.total}`"/><v-list-item title="Pagado" :append-title="`$ ${sale.paid_total}`"/></v-list></div>
  <div class="d-flex ga-2 flex-wrap"><v-btn v-if="sale.allowed_actions?.reserve" @click="action(()=>reserveSale(id))">Reservar</v-btn><v-btn v-if="sale.reservations?.some(r=>r.status==='ACTIVE')" @click="action(()=>releaseReservation(id))">Liberar reserva</v-btn><v-btn v-if="sale.allowed_actions?.confirm" color="primary" @click="action(()=>confirmSale(id))">Confirmar</v-btn><v-btn v-if="sale.allowed_actions?.deliver" color="success" @click="action(()=>deliverSale(id))">Entregar</v-btn></div>
  <v-row class="mt-4"><v-col cols="12" md="4"><v-card variant="outlined"><v-card-title>Pago</v-card-title><v-card-text><v-select v-model="paymentMethod" :items="['efectivo','debito','credito','transferencia','mercadopago']"/><v-text-field v-model.number="paymentAmount" type="number" step="0.01" label="Importe"/><v-btn :disabled="!paymentAmount" @click="action(()=>addPayment(id,{method:paymentMethod,amount:paymentAmount}),'Pago registrado')">Registrar</v-btn></v-card-text></v-card></v-col>
  <v-col cols="12" md="4"><v-card variant="outlined"><v-card-title>Devolución</v-card-title><v-card-text><v-select v-model="returnLineId" :items="sale.lines" item-title="product_name" item-value="id" label="Producto"/><v-text-field v-model.number="returnQty" type="number" step="0.01" label="Cantidad"/><v-textarea v-model="returnReason" label="Motivo"/><v-btn :disabled="!sale.allowed_actions?.return||!returnLineId||!returnQty" @click="returnItem">Registrar</v-btn></v-card-text></v-card></v-col>
  <v-col cols="12" md="4"><v-card variant="outlined"><v-card-title>Anular</v-card-title><v-card-text><v-textarea v-model="reason" label="Motivo"/><v-btn color="error" :disabled="!reason.trim()||!sale.allowed_actions?.annul" @click="action(()=>annulSale(id,reason),'Venta anulada')">Anular</v-btn></v-card-text></v-card></v-col></v-row>
  <v-row class="mt-2"><v-col cols="12" md="6"><v-card variant="outlined"><v-card-title>Adjuntos</v-card-title><v-card-text><v-list><v-list-item v-for="att in sale.attachments" :key="att.id" :title="att.filename" :href="`/media/${att.path}`" target="_blank"><template #append><v-btn icon="mdi-delete" variant="text" @click.prevent="action(()=>deleteAttachment(id,att.id),'Adjunto eliminado')"/></template></v-list-item></v-list><v-file-input v-model="files" multiple label="Agregar archivos"/><v-btn :disabled="!files.length" @click="uploadFiles">Subir</v-btn></v-card-text></v-card></v-col>
  <v-col cols="12" md="6"><v-card variant="outlined"><v-card-title>Timeline</v-card-title><v-card-text><v-timeline side="end" density="compact"><v-timeline-item v-for="(event,index) in timeline" :key="index" size="small"><strong>{{event.type}}</strong><div class="text-caption">{{event.at}}</div></v-timeline-item></v-timeline></v-card-text></v-card></v-col></v-row>
  </v-card-text></v-card><v-skeleton-loader v-else-if="loading" type="article"/>
</v-container></template>
