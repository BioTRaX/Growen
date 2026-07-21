<!-- NG-HEADER: Nombre de archivo: AppShell.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/app/layouts/AppShell.vue -->
<!-- NG-HEADER: Descripción: Shell principal con navegación lateral por rol. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from 'vuetify'

import { navigationFor } from '../modules/registry'
import { useAuthStore } from '../../auth/store'

const drawer = ref(true)
const auth = useAuthStore()
const router = useRouter()
const theme = useTheme()
const items = computed(() => navigationFor(auth.role))

function navigationProps(item: { to: string; runtime: 'legacy' | 'vue' }): { to?: string; href?: string } {
  if (item.runtime === 'legacy' && !import.meta.env.DEV) return { href: item.to }
  return { to: item.to }
}

function toggleTheme(): void {
  const next = theme.global.current.value.dark ? 'growenLight' : 'growenDark'
  theme.global.name.value = next
  localStorage.setItem('ng_theme', next)
}

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <v-navigation-drawer v-model="drawer" width="272">
    <div class="brand pa-5">
      <v-icon color="success" icon="mdi-sprout" size="32" />
      <div>
        <div class="text-h6">Growen</div>
        <div class="text-caption text-medium-emphasis">Vue 3 · migración activa</div>
      </div>
    </div>

    <v-divider />
    <v-list nav density="comfortable">
      <template v-for="entry in items" :key="entry.kind === 'group' ? entry.title : entry.to">
        <v-list-group v-if="entry.kind === 'group'" :value="entry.title">
          <template #activator="{ props }">
            <v-list-item v-bind="props" :prepend-icon="entry.icon" :title="entry.title" rounded="lg" />
          </template>
          <v-list-item
            v-for="item in entry.children"
            :key="item.to"
            :prepend-icon="item.icon"
            :title="item.title"
            v-bind="navigationProps(item)"
            rounded="lg"
          >
            <template v-if="item.migrationState !== 'active'" #append>
              <v-chip color="warning" size="x-small" variant="tonal">{{ item.migrationState }}</v-chip>
            </template>
          </v-list-item>
        </v-list-group>
        <v-list-item
          v-else
          :prepend-icon="entry.icon"
          :title="entry.title"
          v-bind="navigationProps(entry)"
          rounded="lg"
        >
          <template v-if="entry.migrationState !== 'active'" #append>
            <v-chip color="warning" size="x-small" variant="tonal">{{ entry.migrationState }}</v-chip>
          </template>
        </v-list-item>
      </template>
    </v-list>
  </v-navigation-drawer>

  <v-app-bar border="b" elevation="0">
    <v-app-bar-nav-icon aria-label="Alternar navegación" @click="drawer = !drawer" />
    <v-app-bar-title>{{ $route.meta.title ?? 'Growen' }}</v-app-bar-title>
    <v-chip class="mr-3" size="small" variant="tonal">{{ auth.role }}</v-chip>
    <v-btn icon="mdi-theme-light-dark" aria-label="Cambiar tema" @click="toggleTheme" />
    <v-btn v-if="auth.isAuthenticated" class="mr-3" prepend-icon="mdi-logout" @click="logout">Salir</v-btn>
    <v-btn v-else class="mr-3" to="/login" prepend-icon="mdi-account-switch">Cambiar usuario</v-btn>
  </v-app-bar>

  <v-main>
    <router-view />
  </v-main>
</template>

<style scoped lang="scss">
.brand {
  display: flex;
  align-items: center;
  gap: 0.875rem;
}
</style>
