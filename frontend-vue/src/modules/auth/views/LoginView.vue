<!-- NG-HEADER: Nombre de archivo: LoginView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/auth/views/LoginView.vue -->
<!-- NG-HEADER: Descripción: Inicio de sesión Vue conectado al backend existente. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../../../auth/store'

const identifier = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

async function submit(): Promise<void> {
  errorMessage.value = ''
  loading.value = true
  try {
    await auth.login(identifier.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (error: unknown) {
    const status = (error as { response?: { status?: number } }).response?.status
    errorMessage.value = status === 401
      ? 'Usuario o contraseña inválidos'
      : status === 429
        ? 'Demasiados intentos. Esperá unos minutos.'
        : 'No fue posible iniciar sesión.'
  } finally {
    loading.value = false
  }
}

async function enterAsGuest(): Promise<void> {
  errorMessage.value = ''
  loading.value = true
  try {
    await auth.loginAsGuest()
    await router.replace('/guest')
  } catch {
    errorMessage.value = 'No fue posible iniciar la sesión de invitado.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-main class="login-background">
    <v-container class="fill-height justify-center">
      <v-card class="pa-6" elevation="12" max-width="430" width="100%">
        <div class="text-center mb-6">
          <v-icon color="success" icon="mdi-sprout" size="48" />
          <h1 class="text-h4 mt-2">Growen</h1>
          <p class="text-body-2 text-medium-emphasis">Ingresá para continuar</p>
        </div>

        <v-form @submit.prevent="submit">
          <v-text-field v-model="identifier" autofocus label="Usuario o email" prepend-inner-icon="mdi-account-outline" />
          <v-text-field v-model="password" label="Contraseña" prepend-inner-icon="mdi-lock-outline" type="password" />
          <v-alert v-if="errorMessage" class="mb-4" density="compact" type="error" variant="tonal">{{ errorMessage }}</v-alert>
          <v-btn :loading="loading" block color="primary" size="large" type="submit">Ingresar</v-btn>
          <v-btn :disabled="loading" block class="mt-3" variant="outlined" @click="enterAsGuest">Ingresar como invitado</v-btn>
        </v-form>
      </v-card>
    </v-container>
  </v-main>
</template>

<style scoped lang="scss">
.login-background {
  background:
    radial-gradient(circle at 20% 10%, rgba(124, 77, 255, 0.2), transparent 32rem),
    radial-gradient(circle at 80% 90%, rgba(34, 197, 94, 0.14), transparent 28rem);
}
</style>
