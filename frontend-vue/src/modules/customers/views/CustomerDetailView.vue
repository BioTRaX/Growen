<!-- NG-HEADER: Nombre de archivo: CustomerDetailView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/customers/views/CustomerDetailView.vue -->
<!-- NG-HEADER: Descripción: Ficha 360 de cliente, ventas y cuenta corriente. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { useRoute } from 'vue-router'
import { getCustomer, getCustomerAccount, getCustomerSales, updateCustomer, type Customer } from '../../../services/customers'; import { getHttpErrorMessage } from '../../../services/http'
const id=Number(useRoute().params.id); const customer=ref<Customer|null>(null); const sales=ref<any[]>([]); const account=ref<any>({items:[],balance:0}); const loading=ref(false); const error=ref(''); const success=ref('')
async function load(){loading.value=true; try{const [detail,saleData,accountData]=await Promise.all([getCustomer(id),getCustomerSales(id),getCustomerAccount(id)]);customer.value=detail;sales.value=saleData.items;account.value=accountData}catch(e){error.value=getHttpErrorMessage(e)}finally{loading.value=false}}
async function save(){if(!customer.value)return; try{await updateCustomer(id,customer.value);success.value='Cliente actualizado';await load()}catch(e){error.value=getHttpErrorMessage(e)}} onMounted(load)
</script>
<template><v-container fluid class="py-8"><v-btn class="mb-4" variant="text" to="/clientes" prepend-icon="mdi-arrow-left">Clientes</v-btn><v-alert v-if="error" type="error" class="mb-4">{{error}}</v-alert><v-alert v-if="success" type="success" class="mb-4">{{success}}</v-alert>
<v-row v-if="customer"><v-col cols="12" lg="5"><v-card><v-card-title>{{customer.name}}</v-card-title><v-card-text><v-text-field v-model="customer.name" label="Nombre"/><v-text-field v-model="customer.email" label="Email"/><v-text-field v-model="customer.phone" label="Teléfono"/><v-text-field v-model="customer.address" label="Dirección"/><v-text-field v-model.number="customer.credit_limit" type="number" label="Límite de crédito"/><v-btn color="primary" @click="save">Guardar</v-btn></v-card-text></v-card></v-col>
<v-col cols="12" lg="7"><v-row><v-col v-for="(value,key) in customer.metrics" :key="key" cols="6" md="4"><v-card><v-card-text><div class="text-caption">{{key}}</div><div class="text-h6">{{typeof value==='number'?value.toLocaleString('es-AR'):value||'-'}}</div></v-card-text></v-card></v-col></v-row>
<v-card class="mt-4"><v-card-title>Cuenta corriente · $ {{Number(account.balance||0).toLocaleString('es-AR')}}</v-card-title><v-data-table :items="account.items" :headers="[{title:'Fecha',key:'occurred_at'},{title:'Tipo',key:'entry_type'},{title:'Importe',key:'amount'},{title:'Nota',key:'note'}]" /></v-card>
<v-card class="mt-4"><v-card-title>Ventas</v-card-title><v-list><v-list-item v-for="sale in sales" :key="sale.id" :to="`/ventas/${sale.id}`" :title="`Venta #${sale.id} · $ ${sale.total}`" :subtitle="`${sale.status} · ${new Date(sale.sale_date).toLocaleDateString()}`"/></v-list></v-card></v-col></v-row><v-skeleton-loader v-else-if="loading" type="article"/></v-container></template>
