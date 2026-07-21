<!-- NG-HEADER: Nombre de archivo: ToastHost.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/app/notifications/ToastHost.vue -->
<!-- NG-HEADER: Descripción: Host global de notificaciones Vuetify. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { useToastStore } from './store'

const toasts = useToastStore()
</script>

<template>
  <div class="toast-host">
    <v-snackbar
      v-for="item in toasts.items"
      :key="item.id"
      :model-value="true"
      :color="item.kind"
      :timeout="item.timeout"
      location="top right"
      @update:model-value="(visible) => { if (!visible) toasts.dismiss(item.id) }"
    >
      {{ item.text }}
      <template #actions>
        <v-btn variant="text" @click="toasts.dismiss(item.id)">Cerrar</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  inset: 0;
  z-index: 2500;
  pointer-events: none;
}
</style>
