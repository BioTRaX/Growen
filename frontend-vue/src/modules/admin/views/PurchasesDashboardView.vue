<!-- NG-HEADER: Nombre de archivo: PurchasesDashboardView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/PurchasesDashboardView.vue -->
<!-- NG-HEADER: Descripción: Dashboard analítico de compras de colaboradores a costo vs clientes en administración. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getPurchasesSummary, type PurchasesSummaryReport } from '../../../services/sales'
import { getHttpErrorMessage } from '../../../services/http'

const report = ref<PurchasesSummaryReport | null>(null)
const loading = ref(false)
const error = ref('')

const activeTab = ref('comparative')
const quickRange = ref('30d')
const dtFrom = ref('')
const dtTo = ref('')
const statusFilter = ref<string | null>(null)

function setQuickRange(range: string) {
  quickRange.value = range
  const now = new Date()
  const todayStr = now.toISOString().slice(0, 10)

  if (range === 'today') {
    dtFrom.value = todayStr
    dtTo.value = todayStr
  } else if (range === '7d') {
    const d = new Date(now)
    d.setDate(d.getDate() - 7)
    dtFrom.value = d.toISOString().slice(0, 10)
    dtTo.value = todayStr
  } else if (range === '30d') {
    const d = new Date(now)
    d.setDate(d.getDate() - 30)
    dtFrom.value = d.toISOString().slice(0, 10)
    dtTo.value = todayStr
  } else if (range === 'month') {
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
    dtFrom.value = firstDay.toISOString().slice(0, 10)
    dtTo.value = todayStr
  } else if (range === 'all') {
    dtFrom.value = ''
    dtTo.value = ''
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const res = await getPurchasesSummary({
      dt_from: dtFrom.value ? `${dtFrom.value}T00:00:00` : undefined,
      dt_to: dtTo.value ? `${dtTo.value}T23:59:59` : undefined,
      status: statusFilter.value || undefined,
    })
    report.value = res
  } catch (err) {
    error.value = getHttpErrorMessage(err)
  } finally {
    loading.value = false
  }
}

watch([dtFrom, dtTo, statusFilter], () => {
  loadData()
})

onMounted(() => {
  setQuickRange('30d')
  loadData()
})

function formatMoney(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '$ 0'
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0,
  }).format(amount)
}

function formatDate(isoStr: string | null | undefined): string {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  return d.toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getKindColor(kind?: string | null): string {
  if (kind === 'colaborador') return 'purple'
  if (kind === 'mayorista') return 'indigo'
  if (kind === 'minorista') return 'teal'
  if (kind === 'ri') return 'blue'
  return 'grey'
}

function getKindLabel(kind?: string | null): string {
  if (kind === 'colaborador') return 'Colaborador'
  if (kind === 'mayorista') return 'Mayorista'
  if (kind === 'minorista') return 'Minorista'
  if (kind === 'ri') return 'Resp. Inscripto'
  if (kind === 'cf') return 'Consumidor Final'
  return kind || 'Cliente'
}

const summary = computed(() => report.value?.summary)
const collabSummary = computed(() => summary.value?.collaborators)
const custSummary = computed(() => summary.value?.customers)
const totals = computed(() => summary.value?.totals)
const share = computed(() => summary.value?.share)
</script>

<template>
  <v-container fluid class="py-8">
    <!-- Header -->
    <div class="d-flex flex-wrap justify-space-between align-center mb-6 ga-4">
      <div>
        <h1 class="text-h4 font-weight-bold d-flex align-center ga-2">
          <v-icon color="primary">mdi-chart-box-outline</v-icon>
          Compras de Colaboradores y Clientes
        </h1>
        <p class="text-medium-emphasis mb-0">
          Dashboard analítico comparativo: adquisiciones a precio de costo (colaboradores) vs clientes comerciales
        </p>
      </div>
      <div class="d-flex ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="loadData"
        >
          Actualizar
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-cash-register"
          to="/ventas/nueva"
        >
          Nueva Venta
        </v-btn>
      </div>
    </div>

    <!-- Error Alert -->
    <v-alert v-if="error" type="error" class="mb-4" closable @click:close="error = ''">
      {{ error }}
    </v-alert>

    <!-- Barra de Filtros -->
    <v-card class="mb-6" variant="outlined">
      <v-card-text class="py-3">
        <div class="d-flex flex-wrap align-center justify-space-between ga-4">
          <!-- Botones de Período Rápido -->
          <div class="d-flex flex-wrap align-center ga-2">
            <span class="text-caption font-weight-bold text-medium-emphasis mr-1">RANGO:</span>
            <v-btn-toggle
              v-model="quickRange"
              mandatory
              density="compact"
              color="primary"
              variant="outlined"
            >
              <v-btn value="today" @click="setQuickRange('today')">Hoy</v-btn>
              <v-btn value="7d" @click="setQuickRange('7d')">7 días</v-btn>
              <v-btn value="30d" @click="setQuickRange('30d')">30 días</v-btn>
              <v-btn value="month" @click="setQuickRange('month')">Este mes</v-btn>
              <v-btn value="all" @click="setQuickRange('all')">Todo</v-btn>
            </v-btn-toggle>
          </div>

          <!-- Selectores de Fecha y Estado -->
          <div class="d-flex flex-wrap align-center ga-3">
            <v-text-field
              v-model="dtFrom"
              type="date"
              label="Desde"
              density="compact"
              variant="outlined"
              hide-details
              style="min-width: 140px;"
            />
            <v-text-field
              v-model="dtTo"
              type="date"
              label="Hasta"
              density="compact"
              variant="outlined"
              hide-details
              style="min-width: 140px;"
            />
            <v-select
              v-model="statusFilter"
              :items="[
                { title: 'Confirmadas y Entregadas', value: null },
                { title: 'Solo Confirmadas', value: 'CONFIRMADA' },
                { title: 'Solo Entregadas', value: 'ENTREGADA' },
              ]"
              item-title="title"
              item-value="value"
              label="Estado de venta"
              density="compact"
              variant="outlined"
              hide-details
              style="min-width: 190px;"
            />
          </div>
        </div>
      </v-card-text>
    </v-card>

    <!-- KPIs Comparativos Principales -->
    <v-row class="mb-6">
      <!-- Colaboradores KPI Card -->
      <v-col cols="12" md="4">
        <v-card class="h-100 kpi-card-collab" elevation="2">
          <v-card-item>
            <template #prepend>
              <v-avatar color="purple-lighten-4" size="44">
                <v-icon color="purple-darken-2" size="24">mdi-badge-account-outline</v-icon>
              </v-avatar>
            </template>
            <v-card-title class="text-subtitle-1 font-weight-bold">
              Compras de Colaboradores
            </v-card-title>
            <v-card-subtitle class="text-caption text-purple-darken-1 font-weight-medium">
              A precio autoritativo de costo
            </v-card-subtitle>
          </v-card-item>
          <v-card-text class="pt-2">
            <div class="text-h4 font-weight-bold text-purple-darken-3 mb-2">
              {{ formatMoney(collabSummary?.total_amount) }}
            </div>
            <v-divider class="my-3" />
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Compras / Ventas:</span>
              <span class="font-weight-bold">{{ collabSummary?.sales_count ?? 0 }} órdenes</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Unidades adquiridas:</span>
              <span class="font-weight-bold">{{ collabSummary?.units_count ?? 0 }} u.</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Ticket Promedio:</span>
              <span class="font-weight-bold">{{ formatMoney(collabSummary?.avg_ticket) }}</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Colaboradores activos:</span>
              <span class="font-weight-bold">{{ collabSummary?.unique_buyers ?? 0 }}</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Clientes KPI Card -->
      <v-col cols="12" md="4">
        <v-card class="h-100 kpi-card-cust" elevation="2">
          <v-card-item>
            <template #prepend>
              <v-avatar color="blue-lighten-4" size="44">
                <v-icon color="blue-darken-2" size="24">mdi-account-group-outline</v-icon>
              </v-avatar>
            </template>
            <v-card-title class="text-subtitle-1 font-weight-bold">
              Compras de Clientes
            </v-card-title>
            <v-card-subtitle class="text-caption text-blue-darken-1 font-weight-medium">
              Ventas a precio comercial / lista
            </v-card-subtitle>
          </v-card-item>
          <v-card-text class="pt-2">
            <div class="text-h4 font-weight-bold text-blue-darken-3 mb-2">
              {{ formatMoney(custSummary?.total_amount) }}
            </div>
            <v-divider class="my-3" />
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Ventas realizadas:</span>
              <span class="font-weight-bold">{{ custSummary?.sales_count ?? 0 }} órdenes</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Unidades vendidas:</span>
              <span class="font-weight-bold">{{ custSummary?.units_count ?? 0 }} u.</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Ticket Promedio:</span>
              <span class="font-weight-bold">{{ formatMoney(custSummary?.avg_ticket) }}</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 py-1">
              <span class="text-medium-emphasis">Clientes compradores:</span>
              <span class="font-weight-bold">{{ custSummary?.unique_buyers ?? 0 }}</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Participación / Resumen General -->
      <v-col cols="12" md="4">
        <v-card class="h-100" elevation="2">
          <v-card-item>
            <template #prepend>
              <v-avatar color="teal-lighten-4" size="44">
                <v-icon color="teal-darken-2" size="24">mdi-scale-balance</v-icon>
              </v-avatar>
            </template>
            <v-card-title class="text-subtitle-1 font-weight-bold">
              Total y Participación
            </v-card-title>
            <v-card-subtitle class="text-caption text-medium-emphasis">
              Volumen global en el período
            </v-card-subtitle>
          </v-card-item>
          <v-card-text class="pt-2">
            <div class="text-h4 font-weight-bold text-teal-darken-3 mb-2">
              {{ formatMoney(totals?.total_amount) }}
            </div>
            <v-divider class="my-3" />
            <div class="mb-3">
              <div class="d-flex justify-space-between text-caption mb-1">
                <span>Participación en Monto ($)</span>
                <span class="font-weight-bold">
                  Colab: {{ share?.collaborators_amount_pct ?? 0 }}% · Clientes: {{ (100 - (share?.collaborators_amount_pct ?? 0)).toFixed(1) }}%
                </span>
              </div>
              <v-progress-linear
                :model-value="share?.collaborators_amount_pct ?? 0"
                color="purple"
                background-color="blue"
                height="10"
                rounded
              />
            </div>
            <div class="mb-3">
              <div class="d-flex justify-space-between text-caption mb-1">
                <span>Participación en Unidades</span>
                <span class="font-weight-bold">
                  Colab: {{ share?.collaborators_units_pct ?? 0 }}% · Clientes: {{ (100 - (share?.collaborators_units_pct ?? 0)).toFixed(1) }}%
                </span>
              </div>
              <v-progress-linear
                :model-value="share?.collaborators_units_pct ?? 0"
                color="purple"
                background-color="blue"
                height="10"
                rounded
              />
            </div>
            <div class="d-flex justify-space-between text-body-2 pt-1">
              <span class="text-medium-emphasis">Total de Órdenes:</span>
              <span class="font-weight-bold">{{ totals?.sales_count ?? 0 }}</span>
            </div>
            <div class="d-flex justify-space-between text-body-2 pt-1">
              <span class="text-medium-emphasis">Total de Unidades:</span>
              <span class="font-weight-bold">{{ totals?.units_count ?? 0 }} u.</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tabs con Detalles y Desgloses -->
    <v-card elevation="2">
      <v-tabs v-model="activeTab" color="primary" bg-color="surface">
        <v-tab value="comparative">
          <v-icon start>mdi-compare</v-icon>
          Resumen Comparativo
        </v-tab>
        <v-tab value="collaborators">
          <v-icon start color="purple">mdi-badge-account-outline</v-icon>
          Compras de Colaboradores ({{ report?.collaborators.top_buyers.length ?? 0 }})
        </v-tab>
        <v-tab value="customers">
          <v-icon start color="blue">mdi-account-group-outline</v-icon>
          Compras de Clientes ({{ report?.customers.top_buyers.length ?? 0 }})
        </v-tab>
      </v-tabs>

      <v-divider />

      <v-window v-model="activeTab">
        <!-- Pestaña 1: Resumen Comparativo de Productos -->
        <v-window-item value="comparative">
          <v-card-text class="pa-6">
            <v-row>
              <!-- Top Productos Colaboradores -->
              <v-col cols="12" md="6">
                <v-card variant="outlined" class="h-100">
                  <v-card-item>
                    <template #prepend>
                      <v-icon color="purple">mdi-cart-check</v-icon>
                    </template>
                    <v-card-title class="text-subtitle-1 font-weight-bold">
                      Top Productos Adquiridos por Colaboradores
                    </v-card-title>
                    <v-card-subtitle class="text-caption">
                      Ranking por unidades al precio de costo
                    </v-card-subtitle>
                  </v-card-item>
                  <v-table density="comfortable">
                    <thead>
                      <tr>
                        <th>Producto</th>
                        <th class="text-right">Unidades</th>
                        <th class="text-right">Total Costo</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-if="!report?.collaborators.top_products.length">
                        <td colspan="3" class="text-center text-medium-emphasis py-6">
                          No se registran compras de colaboradores en este período.
                        </td>
                      </tr>
                      <tr v-for="prod in report?.collaborators.top_products" :key="prod.product_id">
                        <td class="font-weight-medium">
                          {{ prod.title }}
                        </td>
                        <td class="text-right font-weight-bold text-purple-darken-2">
                          {{ prod.qty }} u.
                        </td>
                        <td class="text-right font-weight-bold">
                          {{ formatMoney(prod.total_amount) }}
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card>
              </v-col>

              <!-- Top Productos Clientes -->
              <v-col cols="12" md="6">
                <v-card variant="outlined" class="h-100">
                  <v-card-item>
                    <template #prepend>
                      <v-icon color="blue">mdi-cart-arrow-right</v-icon>
                    </template>
                    <v-card-title class="text-subtitle-1 font-weight-bold">
                      Top Productos Vendidos a Clientes
                    </v-card-title>
                    <v-card-subtitle class="text-caption">
                      Ranking por unidades a precio comercial
                    </v-card-subtitle>
                  </v-card-item>
                  <v-table density="comfortable">
                    <thead>
                      <tr>
                        <th>Producto</th>
                        <th class="text-right">Unidades</th>
                        <th class="text-right">Facturación</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-if="!report?.customers.top_products.length">
                        <td colspan="3" class="text-center text-medium-emphasis py-6">
                          No se registran ventas a clientes en este período.
                        </td>
                      </tr>
                      <tr v-for="prod in report?.customers.top_products" :key="prod.product_id">
                        <td class="font-weight-medium">
                          {{ prod.title }}
                        </td>
                        <td class="text-right font-weight-bold text-blue-darken-2">
                          {{ prod.qty }} u.
                        </td>
                        <td class="text-right font-weight-bold">
                          {{ formatMoney(prod.total_amount) }}
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-window-item>

        <!-- Pestaña 2: Compras de Colaboradores -->
        <v-window-item value="collaborators">
          <v-card-text class="pa-6">
            <!-- Ranking de Colaboradores -->
            <div class="mb-6">
              <h3 class="text-h6 font-weight-bold mb-1 d-flex align-center ga-2">
                <v-icon color="purple">mdi-trophy-outline</v-icon>
                Ranking de Colaboradores Compradores
              </h3>
              <p class="text-body-2 text-medium-emphasis mb-3">
                Colaboradores ordenados por monto total adquirido al costo
              </p>

              <v-table density="comfortable" class="border rounded">
                <thead>
                  <tr>
                    <th>Colaborador</th>
                    <th class="text-center">Compras Realizadas</th>
                    <th class="text-right">Unidades Totales</th>
                    <th class="text-right">Total al Costo</th>
                    <th class="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!report?.collaborators.top_buyers.length">
                    <td colspan="5" class="text-center text-medium-emphasis py-6">
                      Sin registros de colaboradores para este filtro.
                    </td>
                  </tr>
                  <tr v-for="buyer in report?.collaborators.top_buyers" :key="buyer.customer_id ?? 0">
                    <td>
                      <div class="font-weight-bold text-subtitle-2">{{ buyer.name }}</div>
                      <v-chip size="x-small" color="purple" variant="tonal" class="mt-1">
                        Colaborador · Precio de costo
                      </v-chip>
                    </td>
                    <td class="text-center font-weight-medium">
                      {{ buyer.sales_count }}
                    </td>
                    <td class="text-right font-weight-medium">
                      {{ buyer.units_count }} u.
                    </td>
                    <td class="text-right font-weight-bold text-purple-darken-2">
                      {{ formatMoney(buyer.total_amount) }}
                    </td>
                    <td class="text-center">
                      <v-btn
                        v-if="buyer.customer_id"
                        size="small"
                        variant="text"
                        color="purple"
                        :to="`/clientes/${buyer.customer_id}`"
                        icon="mdi-account-details-outline"
                      />
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </div>

            <!-- Últimas Compras de Colaboradores -->
            <div>
              <h3 class="text-h6 font-weight-bold mb-1 d-flex align-center ga-2">
                <v-icon color="purple">mdi-history</v-icon>
                Últimas Compras de Colaboradores
              </h3>
              <p class="text-body-2 text-medium-emphasis mb-3">
                Detalle reciente de ventas registradas con cliente colaborador
              </p>

              <v-table density="comfortable" class="border rounded">
                <thead>
                  <tr>
                    <th># Orden</th>
                    <th>Fecha</th>
                    <th>Colaborador</th>
                    <th>Estado</th>
                    <th>Pago</th>
                    <th class="text-right">Total al Costo</th>
                    <th class="text-center">Ver</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!report?.collaborators.recent_sales.length">
                    <td colspan="7" class="text-center text-medium-emphasis py-6">
                      Sin órdenes recientes de colaboradores.
                    </td>
                  </tr>
                  <tr v-for="sale in report?.collaborators.recent_sales" :key="sale.id">
                    <td class="font-weight-bold">#{{ sale.id }}</td>
                    <td>{{ formatDate(sale.sale_date) }}</td>
                    <td>{{ sale.customer_name || 'Colaborador' }}</td>
                    <td>
                      <v-chip size="x-small" :color="sale.status === 'ENTREGADA' ? 'success' : 'primary'">
                        {{ sale.status }}
                      </v-chip>
                    </td>
                    <td>
                      <v-chip
                        size="x-small"
                        :color="sale.payment_status === 'PAGADA' ? 'success' : sale.payment_status === 'PARCIAL' ? 'warning' : 'grey'"
                      >
                        {{ sale.payment_status || 'PENDIENTE' }}
                      </v-chip>
                    </td>
                    <td class="text-right font-weight-bold text-purple-darken-2">
                      {{ formatMoney(sale.total) }}
                    </td>
                    <td class="text-center">
                      <v-btn
                        size="small"
                        variant="text"
                        color="primary"
                        :to="`/ventas/${sale.id}`"
                        icon="mdi-open-in-new"
                      />
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </v-card-text>
        </v-window-item>

        <!-- Pestaña 3: Compras de Clientes -->
        <v-window-item value="customers">
          <v-card-text class="pa-6">
            <!-- Ranking de Clientes Comerciales -->
            <div class="mb-6">
              <h3 class="text-h6 font-weight-bold mb-1 d-flex align-center ga-2">
                <v-icon color="blue">mdi-trophy-outline</v-icon>
                Ranking de Clientes Comerciales
              </h3>
              <p class="text-body-2 text-medium-emphasis mb-3">
                Clientes ordenados por monto total comprado a precio regular
              </p>

              <v-table density="comfortable" class="border rounded">
                <thead>
                  <tr>
                    <th>Cliente</th>
                    <th>Tipo</th>
                    <th class="text-center">Ventas Realizadas</th>
                    <th class="text-right">Unidades Totales</th>
                    <th class="text-right">Total Facturado</th>
                    <th class="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!report?.customers.top_buyers.length">
                    <td colspan="6" class="text-center text-medium-emphasis py-6">
                      Sin registros de clientes comerciales para este filtro.
                    </td>
                  </tr>
                  <tr v-for="buyer in report?.customers.top_buyers" :key="buyer.customer_id ?? 0">
                    <td class="font-weight-bold">
                      {{ buyer.name }}
                    </td>
                    <td>
                      <v-chip size="x-small" :color="getKindColor(buyer.kind)" variant="tonal">
                        {{ getKindLabel(buyer.kind) }}
                      </v-chip>
                    </td>
                    <td class="text-center font-weight-medium">
                      {{ buyer.sales_count }}
                    </td>
                    <td class="text-right font-weight-medium">
                      {{ buyer.units_count }} u.
                    </td>
                    <td class="text-right font-weight-bold text-blue-darken-2">
                      {{ formatMoney(buyer.total_amount) }}
                    </td>
                    <td class="text-center">
                      <v-btn
                        v-if="buyer.customer_id"
                        size="small"
                        variant="text"
                        color="blue"
                        :to="`/clientes/${buyer.customer_id}`"
                        icon="mdi-account-details-outline"
                      />
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </div>

            <!-- Últimas Ventas a Clientes -->
            <div>
              <h3 class="text-h6 font-weight-bold mb-1 d-flex align-center ga-2">
                <v-icon color="blue">mdi-history</v-icon>
                Últimas Ventas a Clientes Comerciales
              </h3>
              <p class="text-body-2 text-medium-emphasis mb-3">
                Historial reciente de ventas a clientes externos
              </p>

              <v-table density="comfortable" class="border rounded">
                <thead>
                  <tr>
                    <th># Orden</th>
                    <th>Fecha</th>
                    <th>Cliente</th>
                    <th>Tipo</th>
                    <th>Estado</th>
                    <th>Pago</th>
                    <th class="text-right">Total</th>
                    <th class="text-center">Ver</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!report?.customers.recent_sales.length">
                    <td colspan="8" class="text-center text-medium-emphasis py-6">
                      Sin órdenes recientes de clientes.
                    </td>
                  </tr>
                  <tr v-for="sale in report?.customers.recent_sales" :key="sale.id">
                    <td class="font-weight-bold">#{{ sale.id }}</td>
                    <td>{{ formatDate(sale.sale_date) }}</td>
                    <td>{{ sale.customer_name || 'Consumidor Final' }}</td>
                    <td>
                      <v-chip size="x-small" :color="getKindColor(sale.customer_kind)" variant="tonal">
                        {{ getKindLabel(sale.customer_kind) }}
                      </v-chip>
                    </td>
                    <td>
                      <v-chip size="x-small" :color="sale.status === 'ENTREGADA' ? 'success' : 'primary'">
                        {{ sale.status }}
                      </v-chip>
                    </td>
                    <td>
                      <v-chip
                        size="x-small"
                        :color="sale.payment_status === 'PAGADA' ? 'success' : sale.payment_status === 'PARCIAL' ? 'warning' : 'grey'"
                      >
                        {{ sale.payment_status || 'PENDIENTE' }}
                      </v-chip>
                    </td>
                    <td class="text-right font-weight-bold text-blue-darken-2">
                      {{ formatMoney(sale.total) }}
                    </td>
                    <td class="text-center">
                      <v-btn
                        size="small"
                        variant="text"
                        color="primary"
                        :to="`/ventas/${sale.id}`"
                        icon="mdi-open-in-new"
                      />
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </v-card-text>
        </v-window-item>
      </v-window>
    </v-card>
  </v-container>
</template>

<style scoped lang="scss">
.kpi-card-collab {
  border-left: 4px solid rgb(var(--v-theme-purple, 156, 39, 176));
}

.kpi-card-cust {
  border-left: 4px solid rgb(var(--v-theme-blue, 33, 150, 243));
}
</style>
