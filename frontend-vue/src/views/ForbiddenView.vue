<!-- NG-HEADER: Nombre de archivo: ForbiddenView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/views/ForbiddenView.vue -->
<!-- NG-HEADER: Descripción: Pantalla de acceso denegado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<template>
  <v-main>
    <v-container class="fill-height justify-center">
      <v-empty-state icon="mdi-shield-lock-outline" headline="403" title="Acceso denegado" text="Tu rol no tiene permisos para esta sección.">
        <template #actions><v-btn color="primary" to="/">Volver al inicio</v-btn></template>
      </v-empty-state>
    </v-container>
  </v-main>
</template>
