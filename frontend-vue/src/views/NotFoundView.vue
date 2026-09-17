<!-- NG-HEADER: Nombre de archivo: NotFoundView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/views/NotFoundView.vue -->
<!-- NG-HEADER: Descripción: Pantalla de página no encontrada (404). -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<template>
  <v-main>
    <v-container class="fill-height justify-center py-12">
      <v-empty-state
        icon="mdi-file-search-outline"
        headline="404"
        title="Página no encontrada"
        text="La sección solicitada no existe o fue reubicada dentro del sistema."
      >
        <template #actions>
          <v-btn color="primary" to="/" variant="flat">Volver al inicio</v-btn>
        </template>
      </v-empty-state>
    </v-container>
  </v-main>
</template>
