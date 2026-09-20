<!-- NG-HEADER: Nombre de archivo: PurchaseNewView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/purchases/views/PurchaseNewView.vue -->
<!-- NG-HEADER: Descripción: Alta manual mínima de una compra. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import SupplierSelect from '../../suppliers/components/SupplierSelect.vue'
import { getHttpErrorMessage } from '../../../services/http'
import { createPurchase } from '../../../services/purchases'
const router = useRouter()
const supplierId = ref<number | null>(null); const remito = ref(''); const date = ref(new Date().toISOString().slice(0, 10)); const error = ref('')
async function create() { try { const result = await createPurchase({ supplier_id: supplierId.value, remito_number: remito.value, remito_date: date.value }); await router.push(`/compras/${result.id}`) } catch (cause) { error.value = getHttpErrorMessage(cause, 'No se pudo crear') } }
</script>
<template><v-container class="py-8"><h1 class="text-h4 mb-6">Nueva compra</h1><v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert><v-card><v-card-text><SupplierSelect v-model="supplierId"/><v-text-field v-model="remito" label="Número de remito"/><v-text-field v-model="date" label="Fecha" type="date"/><v-btn color="primary" :disabled="!supplierId || !remito" @click="create">Crear borrador</v-btn></v-card-text></v-card></v-container></template>
