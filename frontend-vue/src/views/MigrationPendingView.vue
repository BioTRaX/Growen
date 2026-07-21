<!-- NG-HEADER: Nombre de archivo: MigrationPendingView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/views/MigrationPendingView.vue -->
<!-- NG-HEADER: Descripción: Estado explícito para módulos todavía servidos por React. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<template>
  <v-container class="py-12">
    <v-empty-state
      headline="Módulo pendiente de migración"
      icon="mdi-hammer-wrench"
      title="Esta ruta ya tiene contrato y permisos en Vue"
      text="La implementación funcional continúa disponible en el frontend React mientras completamos la migración incremental."
    >
      <template #actions>
        <v-btn color="primary" to="/" variant="flat">Volver al inicio</v-btn>
      </template>
    </v-empty-state>
  </v-container>
</template>
