<!-- NG-HEADER: Nombre de archivo: ErrorBoundary.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/app/errors/ErrorBoundary.vue -->
<!-- NG-HEADER: Descripción: Límite global de errores con fallback y reporte de diagnóstico. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'
import { useRoute } from 'vue-router'

import { moduleForPath } from '../modules/manifest'
import { frontendRelease, http, requestDiagnostics } from '../../services/http'

const route = useRoute()
const failed = ref(false)
const reload = () => window.location.reload()

onErrorCaptured((error, _instance, info) => {
  failed.value = true
  const lastRequest = requestDiagnostics()[0]
  void http.post('/debug/frontend/log-error', {
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : undefined,
    componentStack: info,
    url: window.location.href,
    route: route.fullPath,
    module: moduleForPath(route.path)?.id,
    correlationId: lastRequest?.correlationId,
    release: frontendRelease,
    userAgent: navigator.userAgent,
  }).catch(() => undefined)
  return false
})
</script>

<template>
  <slot v-if="!failed" />
  <v-main v-else class="d-flex align-center justify-center pa-6">
    <v-card max-width="560" class="pa-6 text-center">
      <v-icon icon="mdi-alert-circle-outline" size="48" color="error" />
      <h1 class="text-h5 mt-3">No pudimos mostrar esta pantalla</h1>
      <p class="text-body-2 mt-2">El error fue registrado con el contexto de la versión actual.</p>
      <v-btn class="mt-4" color="primary" @click="reload">Recargar</v-btn>
    </v-card>
  </v-main>
</template>
