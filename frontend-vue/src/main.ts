// NG-HEADER: Nombre de archivo: main.ts
// NG-HEADER: Ubicación: frontend-vue/src/main.ts
// NG-HEADER: Descripción: Punto de entrada de Vue, Pinia, Router y Vuetify.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'
import './styles/globals.scss'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './app/router'
import { vuetify } from './app/providers/vuetify'
import { useAuthStore } from './auth/store'

const pinia = createPinia()
createApp(App).use(pinia).use(router).use(vuetify).mount('#app')

window.addEventListener('growen:unauthorized', () => {
  const auth = useAuthStore(pinia)
  auth.clearSession()
  if (router.currentRoute.value.name !== 'login') void router.replace({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
})
