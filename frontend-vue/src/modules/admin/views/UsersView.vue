<!-- NG-HEADER: Nombre de archivo: UsersView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/UsersView.vue -->
<!-- NG-HEADER: Descripción: Administración de usuarios, roles, proveedores y credenciales. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { createUser, deleteUser, listUsers, resetUserPassword, updateUser, type AdminUser, type AdminUserPayload } from '../../../services/adminCore'
import { searchSuppliers, type SupplierSummary } from '../../../services/suppliers'
import { getHttpErrorMessage } from '../../../services/http'
import { useToastStore } from '../../../app/notifications/store'

const roles = ['cliente', 'proveedor', 'colaborador', 'admin']
const rows = ref<AdminUser[]>([]); const suppliers = ref<SupplierSummary[]>([])
const q = ref(''); const role = ref(''); const loading = ref(false); const error = ref('')
const dialog = ref(false); const editing = ref<AdminUser>(); const confirmDelete = ref<AdminUser>(); const generatedPassword = ref('')
const form = ref<AdminUserPayload>({ identifier: '', email: '', name: '', password: '', role: 'cliente' })
const toasts = useToastStore(); let timer: ReturnType<typeof setTimeout> | undefined

async function refresh() { loading.value = true; try { rows.value = await listUsers(q.value, role.value) } catch (e) { error.value = getHttpErrorMessage(e) } finally { loading.value = false } }
async function findSuppliers(value = '') { try { suppliers.value = await searchSuppliers(value) } catch { suppliers.value = [] } }
function openCreate() { editing.value = undefined; form.value = { identifier: '', email: '', name: '', password: '', role: 'cliente' }; dialog.value = true }
function openEdit(user: AdminUser) { editing.value = user; form.value = { email: user.email ?? '', name: user.name ?? '', role: user.role, supplier_id: user.supplier_id ?? undefined }; dialog.value = true }
async function save() { try { if (editing.value) await updateUser(editing.value.id, form.value); else await createUser(form.value); dialog.value = false; toasts.show('Usuario guardado', 'success'); await refresh() } catch (e) { error.value = getHttpErrorMessage(e) } }
async function remove() { const user = confirmDelete.value; confirmDelete.value = undefined; if (!user) return; try { await deleteUser(user.id); toasts.show('Usuario eliminado', 'success'); await refresh() } catch (e) { error.value = getHttpErrorMessage(e) } }
async function resetPassword(user: AdminUser) { try { generatedPassword.value = (await resetUserPassword(user.id)).password } catch (e) { error.value = getHttpErrorMessage(e) } }

watch([q, role], () => { clearTimeout(timer); timer = setTimeout(refresh, 300) }); onMounted(() => { void refresh(); void findSuppliers() })
</script>

<template><v-container fluid class="py-8">
  <div class="d-flex justify-space-between align-center mb-6"><div><h1 class="text-h4">Usuarios</h1><p class="text-medium-emphasis">Identidades, roles y vinculación con proveedores</p></div><v-btn color="primary" prepend-icon="mdi-account-plus" @click="openCreate">Nuevo usuario</v-btn></div>
  <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{ error }}</v-alert>
  <v-card><v-card-text class="d-flex ga-3"><v-text-field v-model="q" label="Buscar" prepend-inner-icon="mdi-magnify" hide-details clearable/><v-select v-model="role" :items="roles" label="Rol" hide-details clearable/></v-card-text>
  <v-data-table :items="rows" :loading="loading" :headers="[{title:'ID',key:'id'},{title:'Identificador',key:'identifier'},{title:'Nombre',key:'name'},{title:'Email',key:'email'},{title:'Rol',key:'role'},{title:'Proveedor',key:'supplier_id'},{title:'',key:'actions',sortable:false}]">
    <template #item.role="{item}"><v-chip size="small">{{ item.role }}</v-chip></template><template #item.actions="{item}"><v-btn size="small" variant="text" @click="openEdit(item)">Editar</v-btn><v-btn size="small" variant="text" @click="resetPassword(item)">Reset</v-btn><v-btn size="small" variant="text" color="error" @click="confirmDelete=item">Eliminar</v-btn></template>
  </v-data-table></v-card>
  <v-dialog v-model="dialog" max-width="720"><v-card><v-card-title>{{ editing?'Editar usuario':'Nuevo usuario' }}</v-card-title><v-card-text><v-row><v-col v-if="!editing" cols="6"><v-text-field v-model="form.identifier" label="Identificador *"/></v-col><v-col v-if="!editing" cols="6"><v-text-field v-model="form.password" type="password" label="Contraseña *"/></v-col><v-col cols="6"><v-text-field v-model="form.name" label="Nombre"/></v-col><v-col cols="6"><v-text-field v-model="form.email" label="Email"/></v-col><v-col cols="6"><v-select v-model="form.role" :items="roles" label="Rol"/></v-col><v-col cols="6"><v-autocomplete v-model="form.supplier_id" :items="suppliers" item-title="name" item-value="id" label="Proveedor" clearable @update:search="findSuppliers"/></v-col></v-row></v-card-text><v-card-actions><v-spacer/><v-btn @click="dialog=false">Cancelar</v-btn><v-btn color="primary" :disabled="!editing && (!form.identifier || !form.password)" @click="save">Guardar</v-btn></v-card-actions></v-card></v-dialog>
  <v-dialog :model-value="!!confirmDelete" max-width="460" @update:model-value="(v)=>{if(!v)confirmDelete=undefined}"><v-card><v-card-title>Eliminar usuario</v-card-title><v-card-text>La eliminación de {{ confirmDelete?.identifier }} es irreversible.</v-card-text><v-card-actions><v-spacer/><v-btn @click="confirmDelete=undefined">Cancelar</v-btn><v-btn color="error" @click="remove">Eliminar</v-btn></v-card-actions></v-card></v-dialog>
  <v-dialog :model-value="!!generatedPassword" max-width="520" @update:model-value="(v)=>{if(!v)generatedPassword=''}"><v-card><v-card-title>Nueva contraseña</v-card-title><v-card-text>Copiar y entregar por un canal seguro. No volverá a mostrarse.<v-text-field class="mt-4" :model-value="generatedPassword" readonly/></v-card-text><v-card-actions><v-spacer/><v-btn @click="generatedPassword=''">Cerrar</v-btn></v-card-actions></v-card></v-dialog>
</v-container></template>
