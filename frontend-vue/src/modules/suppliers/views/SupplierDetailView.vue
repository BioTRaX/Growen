<!-- NG-HEADER: Nombre de archivo: SupplierDetailView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/suppliers/views/SupplierDetailView.vue -->
<!-- NG-HEADER: Descripción: Detalle, edición y gestión de archivos adjuntos de proveedor en Vue 3. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../../auth/store'
import { getHttpErrorMessage } from '../../../services/http'
import { apiUrl } from '../../../services/transports'
import {
  getSupplier,
  updateSupplier,
  listSupplierFiles,
  uploadSupplierFile,
  type Supplier,
  type SupplierFileMeta,
  type SupplierUpdatePayload,
} from '../../../services/suppliers'

const route = useRoute()
const auth = useAuthStore()

const supplierId = computed(() => Number(route.params.id))
const supplier = ref<Supplier | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')

const isEditing = ref(false)
const form = ref<SupplierUpdatePayload>({
  name: '',
  location: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  notes: '',
})

// Gestión de archivos
const files = ref<SupplierFileMeta[]>([])
const filesLoading = ref(false)
const uploading = ref(false)
const uploadError = ref('')
const uploadNotes = ref('')
const selectedFile = ref<File | File[] | null>(null)

const canEdit = computed(() => auth.role === 'admin' || auth.role === 'colaborador')

function getFileToUpload(): File | null {
  if (Array.isArray(selectedFile.value)) {
    return selectedFile.value[0] ?? null
  }
  return selectedFile.value
}

function initForm(data: Supplier) {
  form.value = {
    name: data.name || '',
    location: data.location || '',
    contact_name: data.contact_name || '',
    contact_email: data.contact_email || '',
    contact_phone: data.contact_phone || '',
    notes: data.notes || '',
  }
}

async function fetchSupplier() {
  if (!supplierId.value || isNaN(supplierId.value)) {
    error.value = 'Identificador de proveedor inválido'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await getSupplier(supplierId.value)
    supplier.value = data
    initForm(data)
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudo cargar el proveedor')
  } finally {
    loading.value = false
  }
}

async function fetchFiles() {
  if (!supplierId.value || isNaN(supplierId.value)) return
  filesLoading.value = true
  uploadError.value = ''
  try {
    files.value = await listSupplierFiles(supplierId.value)
  } catch (cause) {
    uploadError.value = getHttpErrorMessage(cause, 'No se pudieron cargar los archivos adjuntos')
  } finally {
    filesLoading.value = false
  }
}

async function saveChanges() {
  if (!supplier.value) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const updated = await updateSupplier(supplierId.value, form.value)
    supplier.value = updated
    initForm(updated)
    isEditing.value = false
    message.value = 'Proveedor actualizado con éxito'
  } catch (cause) {
    error.value = getHttpErrorMessage(cause, 'No se pudieron guardar los cambios')
  } finally {
    saving.value = false
  }
}

function cancelEdit() {
  if (supplier.value) {
    initForm(supplier.value)
  }
  isEditing.value = false
}

async function handleUpload() {
  const file = getFileToUpload()
  if (!file || !supplierId.value) return
  uploading.value = true
  uploadError.value = ''
  try {
    const res = await uploadSupplierFile(supplierId.value, file, uploadNotes.value.trim() || undefined)
    if (res.duplicate) {
      uploadError.value = 'Aviso: El archivo ya existía previamente (hash coincidente)'
    }
    selectedFile.value = null
    uploadNotes.value = ''
    await fetchFiles()
  } catch (cause) {
    uploadError.value = getHttpErrorMessage(cause, 'No se pudo subir el archivo')
  } finally {
    uploading.value = false
  }
}

function formatSize(bytes?: number | null): string {
  if (!bytes) return '-'
  return `${(bytes / 1024).toFixed(1)} KB`
}

function formatDate(iso?: string | null): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('es-AR')
  } catch {
    return iso
  }
}

onMounted(async () => {
  await fetchSupplier()
  await fetchFiles()
})
</script>

<template>
  <v-container fluid class="py-8">
    <!-- Barra superior y navegación -->
    <div class="d-flex align-center justify-space-between mb-6 flex-wrap ga-4">
      <div>
        <div class="text-caption text-medium-emphasis mb-1">Proveedores › Detalle</div>
        <h1 class="text-h4" v-if="supplier">Proveedor: {{ supplier.name }}</h1>
        <h1 class="text-h4" v-else>Proveedor</h1>
      </div>
      <div class="d-flex ga-2">
        <v-btn variant="outlined" prepend-icon="mdi-arrow-left" to="/proveedores">Volver</v-btn>
        <template v-if="canEdit && supplier">
          <v-btn
            v-if="!isEditing"
            color="primary"
            prepend-icon="mdi-pencil"
            @click="isEditing = true"
          >
            Editar
          </v-btn>
          <template v-else>
            <v-btn variant="text" :disabled="saving" @click="cancelEdit">Cancelar</v-btn>
            <v-btn
              color="primary"
              prepend-icon="mdi-content-save"
              :loading="saving"
              @click="saveChanges"
            >
              Guardar cambios
            </v-btn>
          </template>
        </template>
      </div>
    </div>

    <!-- Alertas -->
    <v-alert v-if="error" type="error" class="mb-4" closable @click:close="error = ''">{{ error }}</v-alert>
    <v-alert v-if="message" type="success" class="mb-4" closable @click:close="message = ''">{{ message }}</v-alert>

    <!-- Indicador de carga -->
    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="primary" size="48" />
      <p class="text-medium-emphasis mt-4">Cargando información del proveedor...</p>
    </div>

    <template v-else-if="supplier">
      <!-- Ficha de Datos Principales -->
      <v-row class="mb-6">
        <v-col cols="12" md="4">
          <v-card class="h-100">
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-card-account-details-outline" size="small" />
              Datos identificatorios
            </v-card-title>
            <v-card-text>
              <v-text-field
                label="Identificador (slug)"
                :model-value="supplier.slug"
                disabled
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="form.name"
                label="Nombre"
                :disabled="!isEditing"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="form.location"
                label="Ubicación"
                :disabled="!isEditing"
                density="compact"
              />
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="4">
          <v-card class="h-100">
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-contacts-outline" size="small" />
              Contacto
            </v-card-title>
            <v-card-text>
              <v-text-field
                v-model="form.contact_name"
                label="Nombre de contacto"
                :disabled="!isEditing"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="form.contact_email"
                label="Correo electrónico"
                :disabled="!isEditing"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="form.contact_phone"
                label="Teléfono"
                :disabled="!isEditing"
                density="compact"
              />
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="4">
          <v-card class="h-100">
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-note-text-outline" size="small" />
              Notas
            </v-card-title>
            <v-card-text>
              <v-textarea
                v-model="form.notes"
                label="Notas y observaciones"
                :disabled="!isEditing"
                rows="6"
                density="compact"
                hide-details
              />
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Archivos adjuntos y documentación -->
      <v-card class="mb-6">
        <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
          <div class="d-flex align-center ga-2">
            <v-icon icon="mdi-file-multiple-outline" />
            <span>Archivos y listas asociadas</span>
          </div>
          <v-chip size="small" variant="tonal" color="info">
            {{ files.length }} archivo(s)
          </v-chip>
        </v-card-title>
        <v-card-subtitle>
          Formatos permitidos: PDF, TXT, CSV, XLS, XLSX, ODS, PNG, JPG, JPEG, WEBP (hasta 10 MB)
        </v-card-subtitle>

        <v-card-text>
          <v-alert v-if="uploadError" type="warning" class="mb-4" closable @click:close="uploadError = ''">
            {{ uploadError }}
          </v-alert>

          <!-- Zona de subida de archivos (solo staff) -->
          <div v-if="canEdit" class="d-flex flex-column flex-md-row ga-3 align-start mb-6">
            <v-file-input
              v-model="selectedFile"
              label="Seleccionar archivo"
              accept=".pdf,.txt,.csv,.xls,.xlsx,.ods,.png,.jpg,.jpeg,.webp"
              density="compact"
              hide-details
              class="flex-grow-1"
            />
            <v-text-field
              v-model="uploadNotes"
              label="Descripción o notas del archivo (opcional)"
              density="compact"
              hide-details
              class="flex-grow-1"
            />
            <v-btn
              color="primary"
              prepend-icon="mdi-upload"
              :disabled="!selectedFile"
              :loading="uploading"
              @click="handleUpload"
            >
              Subir
            </v-btn>
          </div>

          <!-- Tabla de archivos -->
          <v-data-table
            :headers="[
              { title: 'Nombre de archivo', key: 'original_name' },
              { title: 'Tamaño', key: 'size_bytes', align: 'end' },
              { title: 'Fecha de subida', key: 'uploaded_at', align: 'center' },
              { title: '', key: 'actions', align: 'end', sortable: false },
            ]"
            :items="files"
            :loading="filesLoading"
            no-data-text="No hay archivos adjuntos cargados para este proveedor."
          >
            <template #item.original_name="{ item }">
              <span class="font-weight-medium" :title="item.filename">{{ item.original_name }}</span>
            </template>
            <template #item.size_bytes="{ item }">
              {{ formatSize(item.size_bytes) }}
            </template>
            <template #item.uploaded_at="{ item }">
              {{ formatDate(item.uploaded_at) }}
            </template>
            <template #item.actions="{ item }">
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-download"
                :href="apiUrl(`/suppliers/files/${item.id}/download`)"
                target="_blank"
                rel="noopener noreferrer"
              >
                Descargar
              </v-btn>
            </template>
          </v-data-table>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>
