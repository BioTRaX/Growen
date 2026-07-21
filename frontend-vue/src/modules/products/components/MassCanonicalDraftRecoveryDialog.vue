<!-- NG-HEADER: Nombre de archivo: MassCanonicalDraftRecoveryDialog.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/MassCanonicalDraftRecoveryDialog.vue -->
<!-- NG-HEADER: Descripción: Confirmación para recuperar o descartar un alta masiva pendiente. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import type { MassCanonicalDraft } from '../types'

defineProps<{ modelValue: boolean; draft: MassCanonicalDraft | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; resume: []; discard: [] }>()
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="560" persistent>
    <v-card>
      <v-card-title>Alta masiva pendiente</v-card-title>
      <v-card-text>
        Encontramos un borrador de {{ draft?.rows.length ?? 0 }} producto(s), guardado
        {{ draft ? new Date(draft.updatedAt).toLocaleString('es-AR') : '' }}.
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn color="error" variant="text" @click="emit('discard')">Descartar</v-btn>
        <v-btn color="primary" @click="emit('resume')">Continuar borrador</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
