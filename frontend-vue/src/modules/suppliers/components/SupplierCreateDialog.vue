<!-- NG-HEADER: Nombre de archivo: SupplierCreateDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/suppliers/components/SupplierCreateDialog.vue -->
<!-- NG-HEADER: Descripción: Alta rápida de proveedores para Compras y Proveedores. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import { createSupplier, type SupplierSummary } from '../../../services/suppliers'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: [supplier: SupplierSummary]
}>()

const name = ref('')
const slug = ref('')
const location = ref('')
const contactName = ref('')
const contactEmail = ref('')
const contactPhone = ref('')
const notes = ref('')
const slugTouched = ref(false)
const loading = ref(false)
const error = ref('')

function slugify(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

watch(name, (value) => {
  if (!slugTouched.value) slug.value = slugify(value)
})

watch(() => props.modelValue, (open) => {
  if (!open) return
  error.value = ''
})

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  if (!name.value.trim() || !slug.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    const supplier = await createSupplier({
      name: name.value.trim(), slug: slug.value.trim(), location: location.value.trim() || null,
      contact_name: contactName.value.trim() || null, contact_email: contactEmail.value.trim() || null,
      contact_phone: contactPhone.value.trim() || null, notes: notes.value.trim() || null,
    })
    emit('created', supplier)
    name.value = ''; slug.value = ''; location.value = ''; contactName.value = ''
    contactEmail.value = ''; contactPhone.value = ''; notes.value = ''; slugTouched.value = false
    close()
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo crear el proveedor')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="680" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Nuevo proveedor</v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
        <v-row>
          <v-col cols="12" md="7"><v-text-field v-model="name" label="Nombre comercial" autofocus /></v-col>
          <v-col cols="12" md="5"><v-text-field v-model="slug" label="Identificador" @update:model-value="slugTouched = true" /></v-col>
          <v-col cols="12"><v-text-field v-model="location" label="Ubicación" /></v-col>
          <v-col cols="12" md="6"><v-text-field v-model="contactName" label="Persona de contacto" /></v-col>
          <v-col cols="12" md="6"><v-text-field v-model="contactPhone" label="Teléfono" /></v-col>
          <v-col cols="12"><v-text-field v-model="contactEmail" label="Correo" type="email" /></v-col>
          <v-col cols="12"><v-textarea v-model="notes" label="Notas" rows="2" /></v-col>
        </v-row>
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn variant="text" @click="close">Cancelar</v-btn>
        <v-btn color="primary" :disabled="!name.trim() || !slug.trim()" :loading="loading" @click="submit">Crear proveedor</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
