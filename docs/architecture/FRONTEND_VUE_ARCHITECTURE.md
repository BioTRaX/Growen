<!-- NG-HEADER: Nombre de archivo: FRONTEND_VUE_ARCHITECTURE.md -->
<!-- NG-HEADER: Ubicación: docs/architecture/FRONTEND_VUE_ARCHITECTURE.md -->
<!-- NG-HEADER: Descripción: Base arquitectónica y decisiones de diseño del frontend Vue 3, Vuetify y SASS -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Arquitectura Frontend Vue 3 de Growen

Documento base preservado desde el diseño original de migración (`frontend/brainstorming_Growen.md`).

## Contexto y alcance

Este documento define la arquitectura implementada en `frontend-vue/` para la evolución a Vue 3 + Vuetify + SASS.

- Estado del repositorio: Frontend unificado al 100% sobre Vue 3; React completamente retirado.
- Alcance: decisiones de arquitectura, layout, patrones de componentes, estilos y estructura modular.

## Technical Stack

Stack objetivo confirmado para la arquitectura frontend:

- Vue 3
- Vite
- Vuetify 3
- SASS/SCSS
- Pinia
- Vue Router 4

Reglas obligatorias de implementación:

- Usar exclusivamente Composition API con `script setup` en todos los componentes.
- No usar Options API.
- Separar claramente presentación, estado y reglas de negocio mediante composables y servicios.

## Arquitectura del Layout Principal

Se define un App Shell con dos zonas principales:

- Sidebar lateral dinámica y colapsable para navegación, contexto de módulo y accesos rápidos.
- Main Content central para renderizar módulos colaborativos independientes.

### Objetivo funcional del Shell

- Permitir incorporar módulos por dominio sin acoplar navegación y vistas globales.
- Soportar cargas diferidas por módulo para mejorar rendimiento inicial.
- Habilitar personalización por rol (admin, colaborador, cliente, proveedor, invitado) en navegación y acciones visibles.

### Contrato de módulo colaborativo

Cada módulo (por ejemplo Catálogo, Stock, Mercado, Ventas, Compras, Auditoría) debe registrar:

- `id`: identificador único de módulo.
- `routes`: rutas del módulo con permisos.
- `roles`: roles habilitados.
- `capabilities`: permisos granulares requeridos.
- `lazyViews`: vistas con carga diferida.

Resultado:

- Sidebar representa navegación viva por plugins mediante el manifiesto modular.
- Main Content renderiza la vista activa del módulo manteniendo aislamiento entre dominios.

## Patrón de Componentes

Se adopta una versión simplificada de Atomic Design con dos capas operativas:

- Componentes: átomos y moléculas reutilizables (`components/`).
- Vistas: páginas de negocio que orquestan componentes y composables (`views/`).

### Convenciones de diseño de componentes

- Componentes de UI sin lógica de negocio compleja.
- Estado derivado y efectos en composables (`useXxx`).
- Comunicación de componente por `props` y `emits` tipados.
- Vistas responsables de composición, permisos y flujo.

### Regla Composition API

- Todos los componentes y vistas deben usar `script setup`.
- Las utilidades compartidas deben exponerse como composables reutilizables.

## Configuración de Estilos

El archivo `settings.scss` es la fuente única de identidad visual y tokens de diseño.

### Responsabilidades de `settings.scss`

- Definir tokens de marca: color, tipografía, espaciado, radios, sombras y elevación.
- Centralizar variables SASS consumidas por Vuetify.
- Evitar duplicación de tokens en componentes individuales.

### Integración con Vuetify

- Inyectar `settings.scss` como configuración base de estilos globales.
- Usar las variables SASS para sobreescribir tema y defaults de Vuetify.
- Mantener coherencia visual entre Sidebar, Main Content y componentes de dominio.

## Estructura modular implementada (`frontend-vue/src/`)

```text
frontend-vue/
  src/
    app/
      layouts/
        AppShell.vue
      modules/
        manifest.ts
        registry.ts
      router/
        index.ts
        access.ts
      providers/
        vuetify.ts
    auth/
      store.ts
      types.ts
      capabilities.ts
    modules/
      admin/
      catalog-audit/
      chat/
      customers/
      dashboard/
      images/
      knowledge/
      market/
      products/
      purchases/
      sales/
      stock/
      suppliers/
    services/
      http.ts
      transports.ts
      ...
    styles/
      settings.scss
      main.scss
```

## Decisiones arquitectónicas clave

- Arquitectura modular con registro único mediante `config/modules.json` y generación estricta de rutas Nginx (`generated/nginx-spa-routes.conf`).
- Shell único (Sidebar + Main Content) como marco de navegación y productividad.
- Composition API con `script setup` como estándar absoluto.
- Descarga segura de adjuntos y medios con `apiUrl()` de `@/services/transports` para prevenir secuestro de URLs por el router SPA.
