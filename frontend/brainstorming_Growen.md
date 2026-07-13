<!-- NG-HEADER: Nombre de archivo: brainstorming_Growen.md -->
<!-- NG-HEADER: Ubicación: frontend/brainstorming_Growen.md -->
<!-- NG-HEADER: Descripción: Base arquitectónica frontend objetivo para Growen con Vue 3, Vuetify y SASS -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Brainstorming Frontend Growen

Última actualización: 2026-06-06

## Contexto y alcance

Este documento define la arquitectura objetivo del frontend de Growen para una evolución hacia Vue 3 + Vuetify + SASS.

- Estado actual del repositorio: frontend implementado en React.
- Estado objetivo de este documento: base de arquitectura y convenciones para una UI dinámica orientada a plugins.
- Alcance: decisiones de arquitectura, layout, patrones de componentes, estilos y estructura de carpetas.

## Technical Stack

Stack objetivo confirmado para la arquitectura frontend:

- Vue 3
- Vite
- Vuetify
- SASS/SCSS

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
- Habilitar personalización por rol (admin, colaborador, invitado) en navegación y acciones visibles.

### Contrato de módulo colaborativo

Cada módulo (por ejemplo Ingesta, Mercado, Pricing) debe registrar:

- `id`: identificador único de módulo.
- `basePath`: prefijo de rutas del módulo.
- `navItems`: entradas para Sidebar.
- `permissions`: roles habilitados.
- `lazyViews`: vistas con carga diferida.

Resultado esperado:

- Sidebar representa navegación viva por plugins.
- Main Content renderiza la vista activa del módulo manteniendo aislamiento entre dominios.

## Patrón de Componentes

Se adopta una versión simplificada de Atomic Design con dos capas operativas:

- Componentes: átomos y moléculas reutilizables.
- Vistas: páginas de negocio que orquestan componentes y composables.

### Convenciones de diseño de componentes

- Componentes de UI sin lógica de negocio compleja.
- Estado derivado y efectos en composables (`useXxx`).
- Comunicación de componente por `props` y `emits` tipados.
- Vistas responsables de composición, permisos y flujo.

### Regla Composition API

- Todos los componentes y vistas deben usar `script setup`.
- Las utilidades compartidas deben exponerse como composables reutilizables.

## Configuración de Estilos

El archivo `settings.scss` será la fuente única de identidad visual y tokens de diseño.

### Responsabilidades de `settings.scss`

- Definir tokens de marca: color, tipografía, espaciado, radios, sombras y elevación.
- Centralizar variables SASS consumidas por Vuetify.
- Evitar duplicación de tokens en componentes individuales.

### Integración con Vuetify

- Inyectar `settings.scss` como configuración base de estilos globales.
- Usar las variables SASS para sobreescribir tema y defaults de Vuetify.
- Mantener coherencia visual entre Sidebar, Main Content y componentes de dominio.

### Reglas de gobernanza visual

- No declarar tokens de marca fuera de `settings.scss`.
- No hardcodear colores/sombras de identidad en componentes.
- Cualquier cambio de branding inicia en `settings.scss` y luego se propaga.

## Estructura de carpetas inicial propuesta

La siguiente estructura soporta la arquitectura plugin-based, Composition API y Atomic simplificado:

```text
frontend/
  src/
    app/
      layouts/
        AppShell.vue
        SidebarLayout.vue
      router/
        index.ts
        guards.ts
      providers/
        vuetify.ts
    modules/
      ingestion/
        views/
          IngestionHomeView.vue
        components/
        composables/
        routes.ts
      market/
        views/
          MarketHomeView.vue
        components/
        composables/
        routes.ts
      pricing/
        views/
          PricingHomeView.vue
        components/
        composables/
        routes.ts
    views/
      DashboardView.vue
      NotFoundView.vue
    components/
      atoms/
      molecules/
    composables/
      useSidebar.ts
      usePermissions.ts
    services/
      api/
      adapters/
    styles/
      settings.scss
      globals.scss
```

## Decisiones arquitectónicas clave

- Arquitectura modular con registro por plugin para escalabilidad colaborativa.
- Shell único (Sidebar + Main Content) como marco de navegación y productividad.
- Composition API con `script setup` como estándar absoluto.
- Atomic simplificado para equilibrio entre reutilización y velocidad de entrega.
- `settings.scss` como punto único de diseño para evitar deriva visual.

## Criterios de aceptación internos para implementación futura

- Todo componente nuevo usa `script setup`.
- Sidebar puede colapsarse y reflejar módulos habilitados por rol.
- Main Content renderiza vistas lazy de módulos independientes.
- Los estilos de marca provienen solo de `settings.scss`.
- La estructura de carpetas se mantiene por dominio y por responsabilidad.
