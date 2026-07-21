<!-- NG-HEADER: Nombre de archivo: App.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/App.vue -->
<!-- NG-HEADER: Descripción: Componente raíz de la SPA Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import ErrorBoundary from './app/errors/ErrorBoundary.vue'
import ToastHost from './app/notifications/ToastHost.vue'
</script>

<template>
  <v-app>
    <ErrorBoundary>
      <router-view />
    </ErrorBoundary>
    <ToastHost />
  </v-app>
</template>
