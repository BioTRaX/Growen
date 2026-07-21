<!-- NG-HEADER: Nombre de archivo: DashboardView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/dashboard/views/DashboardView.vue -->
<!-- NG-HEADER: Descripción: Panel inicial del primer corte migrado a Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '../../../auth/store'
import { navigationItemsFor } from '../../../app/modules/registry'

const auth = useAuthStore()
const modules = computed(() => navigationItemsFor(auth.role).filter((item) => item.to !== '/'))
</script>

<template>
  <v-container class="py-8" fluid>
    <v-row>
      <v-col cols="12">
        <v-card class="hero pa-6" color="surface">
          <v-chip color="success" prepend-icon="mdi-check-circle-outline" variant="tonal">Base Vue operativa</v-chip>
          <h1 class="text-h3 mt-4">Hola{{ auth.user?.name ? `, ${auth.user.name}` : '' }}</h1>
          <p class="text-body-1 text-medium-emphasis mt-2 mb-0">
            El shell, la sesión y las reglas por rol ya funcionan sobre Vue 3 y Vuetify.
          </p>
        </v-card>
      </v-col>

      <v-col v-for="item in modules" :key="item.to" cols="12" md="6" lg="4">
        <v-card :to="item.to" class="h-100 pa-2" hover>
          <v-card-item :prepend-icon="item.icon" :title="item.title">
            <template #append>
              <v-chip :color="item.migrationState === 'active' ? 'success' : 'warning'" size="small" variant="tonal">{{ item.migrationState === 'active' ? 'Operativo' : 'Por migrar' }}</v-chip>
            </template>
          </v-card-item>
          <v-card-text>{{ item.migrationState === 'active' ? 'Módulo funcional disponible en Vue.' : 'La ruta y sus permisos ya están registrados; la vista de negocio continuará en React hasta completar su corte.' }}</v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped lang="scss">
.hero {
  border: 1px solid rgba(var(--v-theme-primary), 0.28);
  background-image: linear-gradient(135deg, rgba(var(--v-theme-primary), 0.12), transparent 55%);
}
</style>
