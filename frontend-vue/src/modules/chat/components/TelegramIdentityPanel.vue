<!-- NG-HEADER: Nombre de archivo: TelegramIdentityPanel.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/chat/components/TelegramIdentityPanel.vue -->
<!-- NG-HEADER: Descripción: Vinculación Telegram y doble aprobación administrativa sin exponer IDs. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import {
  approveExternalIdentity,
  createTelegramLinkRequest,
  getTelegramLinkingStatus,
  listAdminExternalIdentities,
  listMyExternalIdentities,
  revokeAdminExternalIdentity,
  revokeMyExternalIdentity,
  type ExternalIdentity,
  type LinkRequest,
  type TelegramLinkingStatus,
} from '../api/externalIdentities'

const auth = useAuthStore()
const status = ref<TelegramLinkingStatus>()
const mine = ref<ExternalIdentity[]>([])
const all = ref<ExternalIdentity[]>([])
const password = ref('')
const request = ref<LinkRequest>()
const dialog = ref(false)
const loading = ref(false)
const error = ref('')
const canManage = computed(() => auth.isAuthenticated && auth.role !== 'guest')

async function refresh(): Promise<void> {
  if (!canManage.value) return
  loading.value = true
  error.value = ''
  try {
    const [linking, own, adminRows] = await Promise.all([
      getTelegramLinkingStatus(),
      listMyExternalIdentities(),
      auth.role === 'admin' ? listAdminExternalIdentities() : Promise.resolve([]),
    ])
    status.value = linking
    mine.value = own
    all.value = adminRows
  } catch (reason) {
    error.value = getHttpErrorMessage(reason, 'No se pudo consultar la vinculación Telegram')
  } finally {
    loading.value = false
  }
}

async function createRequest(): Promise<void> {
  if (!password.value) return
  loading.value = true
  error.value = ''
  try {
    request.value = await createTelegramLinkRequest(password.value)
    password.value = ''
  } catch (reason) {
    const message = getHttpErrorMessage(reason, 'No se pudo generar el código')
    error.value = message === 'telegram_linking_disabled' ? 'La vinculación Telegram todavía está deshabilitada.' : message
  } finally {
    loading.value = false
  }
}

async function revokeMine(identity: ExternalIdentity): Promise<void> {
  await runAndRefresh(() => revokeMyExternalIdentity(identity.id))
}

async function approve(identity: ExternalIdentity): Promise<void> {
  await runAndRefresh(() => approveExternalIdentity(identity.id))
}

async function revokeAsAdmin(identity: ExternalIdentity): Promise<void> {
  await runAndRefresh(() => revokeAdminExternalIdentity(identity.id))
}

async function runAndRefresh(operation: () => Promise<unknown>): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    await operation()
    await refresh()
  } catch (reason) {
    error.value = getHttpErrorMessage(reason, 'No se pudo actualizar la identidad')
    loading.value = false
  }
}

function closeDialog(): void {
  password.value = ''
  request.value = undefined
  dialog.value = false
}

onMounted(refresh)
</script>

<template>
  <v-card v-if="canManage" class="mb-4" variant="tonal">
    <v-card-item title="Telegram y accesos" subtitle="Los identificadores permanecen cifrados y enmascarados.">
      <template #append><v-btn :loading="loading" icon="mdi-refresh" aria-label="Actualizar vínculos" variant="text" @click="refresh" /></template>
    </v-card-item>
    <v-card-text>
      <v-alert v-if="error" class="mb-3" closable type="error" @click:close="error = ''">{{ error }}</v-alert>
      <v-alert v-if="status && !status.enabled" class="mb-3" type="info" variant="tonal">La vinculación está preparada, pero permanece deshabilitada por seguridad.</v-alert>
      <v-list v-if="mine.length" density="compact">
        <v-list-item v-for="identity in mine" :key="identity.id" :subtitle="identity.status" :title="`${identity.provider} · ${identity.masked_identifier}`">
          <template #append><v-btn v-if="identity.status !== 'revoked'" color="error" size="small" variant="text" @click="revokeMine(identity)">Desvincular</v-btn></template>
        </v-list-item>
      </v-list>
      <p v-else class="text-body-2 text-medium-emphasis">No hay identidades externas vinculadas.</p>
      <v-btn class="mt-2" :disabled="!status?.enabled" prepend-icon="mdi-link-variant" @click="dialog = true">Vincular Telegram</v-btn>
    </v-card-text>

    <v-divider v-if="auth.role === 'admin'" />
    <v-card-text v-if="auth.role === 'admin'">
      <div class="text-subtitle-1 mb-2">Aprobación administrativa</div>
      <v-list v-if="all.length" density="compact">
        <v-list-item v-for="identity in all" :key="identity.id" :subtitle="`Usuario #${identity.user_id ?? '—'} · ${identity.status}`" :title="identity.masked_identifier">
          <template #append><div class="d-flex ga-1"><v-btn v-if="identity.status === 'pending_approval'" :disabled="identity.user_id === auth.user?.id" color="success" size="small" variant="text" @click="approve(identity)">Aprobar</v-btn><v-btn v-if="identity.status !== 'revoked'" color="error" size="small" variant="text" @click="revokeAsAdmin(identity)">Revocar</v-btn></div></template>
        </v-list-item>
      </v-list>
      <p v-else class="text-body-2 text-medium-emphasis">No hay identidades pendientes o activas.</p>
    </v-card-text>
  </v-card>

  <v-dialog v-model="dialog" max-width="560" persistent>
    <v-card title="Vincular Telegram">
      <v-card-text>
        <template v-if="request">
          <v-alert type="warning" variant="tonal">Este código es de un solo uso y vence en cinco minutos. No lo compartas.</v-alert>
          <v-text-field class="mt-4" :model-value="request.command" label="Comando privado" readonly />
        </template>
        <v-text-field v-else v-model="password" autocomplete="current-password" label="Confirmá tu contraseña" type="password" @keyup.enter="createRequest" />
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn variant="text" @click="closeDialog">Cerrar</v-btn><v-btn v-if="!request" color="primary" :disabled="!password" :loading="loading" @click="createRequest">Generar código</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>
