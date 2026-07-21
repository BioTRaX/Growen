<!-- NG-HEADER: Nombre de archivo: BackupsView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/BackupsView.vue -->
<!-- NG-HEADER: Descripción: Listado, ejecución y descarga autenticada de backups. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { downloadBackup, listBackups, runBackup, type BackupItem } from '../../../services/adminCore'
import { getHttpErrorMessage } from '../../../services/http'
import { useToastStore } from '../../../app/notifications/store'
const rows=ref<BackupItem[]>([]); const loading=ref(false); const running=ref(false); const error=ref(''); const confirmRun=ref(false); const toasts=useToastStore()
async function refresh(){loading.value=true;try{rows.value=await listBackups()}catch(e){error.value=getHttpErrorMessage(e)}finally{loading.value=false}}
async function run(){confirmRun.value=false;running.value=true;try{const result=await runBackup();toasts.show(`Backup creado${result.meta?.file?`: ${result.meta.file}`:''}`,'success');await refresh()}catch(e){error.value=getHttpErrorMessage(e)}finally{running.value=false}}
async function download(item:BackupItem){try{await downloadBackup(item.filename)}catch(e){error.value=getHttpErrorMessage(e,'No se pudo descargar el backup')}}
onMounted(refresh)
</script>
<template><v-container fluid class="py-8"><div class="d-flex justify-space-between align-center mb-6"><div><h1 class="text-h4">Backups</h1><p class="text-medium-emphasis">Copias de seguridad administradas</p></div><v-btn color="primary" prepend-icon="mdi-database-plus" :loading="running" @click="confirmRun=true">Backup ahora</v-btn></div><v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{error}}</v-alert><v-card><v-data-table :items="rows" :loading="loading" :headers="[{title:'Archivo',key:'filename'},{title:'Tamaño',key:'size'},{title:'Fecha',key:'modified'},{title:'',key:'actions',sortable:false}]"><template #item.size="{item}">{{(item.size/1024/1024).toFixed(2)}} MB</template><template #item.modified="{item}">{{new Date(item.modified).toLocaleString()}}</template><template #item.actions="{item}"><v-btn variant="text" prepend-icon="mdi-download" @click="download(item)">Descargar</v-btn></template></v-data-table></v-card><v-dialog v-model="confirmRun" max-width="460"><v-card><v-card-title>Crear backup</v-card-title><v-card-text>Se ejecutará una nueva copia de seguridad en el servidor.</v-card-text><v-card-actions><v-spacer/><v-btn @click="confirmRun=false">Cancelar</v-btn><v-btn color="primary" @click="run">Crear</v-btn></v-card-actions></v-card></v-dialog></v-container></template>
