// NG-HEADER: Nombre de archivo: index.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/router/index.ts
// NG-HEADER: Descripción: Router Vue derivado del manifiesto modular y protegido por roles/capacidades.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { createRouter, createWebHistory, type RouteComponent, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '../../auth/store'
import { frontendManifest } from '../modules/manifest'
import { resolveRouteAccess } from './access'

const loaders: Record<string, RouteComponent> = {
  dashboard: () => import('../../modules/dashboard/views/DashboardView.vue'),
  products: () => import('../../modules/products/views/ProductsImpactView.vue'),
  'product-detail': () => import('../../modules/products/views/ProductPurchaseHistoryView.vue'),
  stock: () => import('../../modules/stock/views/StockView.vue'),
  'stock-shortages': () => import('../../modules/stock/views/StockShortagesView.vue'),
  market: () => import('../../modules/market/views/MarketView.vue'),
  purchases: () => import('../../modules/purchases/views/PurchasesView.vue'),
  'purchase-new': () => import('../../modules/purchases/views/PurchaseNewView.vue'),
  'purchase-detail': () => import('../../modules/purchases/views/PurchaseDetailView.vue'),
  suppliers: () => import('../../modules/suppliers/views/SuppliersView.vue'),
  customers: () => import('../../modules/customers/views/CustomersView.vue'),
  'customer-detail': () => import('../../modules/customers/views/CustomerDetailView.vue'),
  sales: () => import('../../modules/sales/views/SalesView.vue'),
  'sale-new': () => import('../../modules/sales/views/SaleNewView.vue'),
  'sale-detail': () => import('../../modules/sales/views/SaleDetailView.vue'),
  'admin-services': () => import('../../modules/admin/views/ServicesView.vue'),
  'admin-workers': () => import('../../modules/admin/views/WorkersView.vue'),
  'admin-mcp': () => import('../../modules/admin/views/McpToolsView.vue'),
  'admin-users': () => import('../../modules/admin/views/UsersView.vue'),
  'admin-backups': () => import('../../modules/admin/views/BackupsView.vue'),
  'admin-drive-sync': () => import('../../modules/admin/views/DriveSyncView.vue'),
  'admin-scheduler': () => import('../../modules/admin/views/SchedulerView.vue'),
  'admin-knowledge': () => import('../../modules/admin/views/KnowledgeView.vue'),
  'admin-image-operations': () => import('../../modules/admin/views/ImageOperationsView.vue'),
  'admin-catalog-diagnostics': () => import('../../modules/admin/views/CatalogDiagnosticsView.vue'),
  'admin-technical-dashboard': () => import('../../modules/admin/views/TechnicalDashboardView.vue'),
  'admin-chat-inbox': () => import('../../modules/admin/views/ChatInboxView.vue'),
  'product-images': () => import('../../modules/images/views/ProductImagesView.vue'),
  pending: () => import('../../views/MigrationPendingView.vue'),
}

const moduleRoutes: RouteRecordRaw[] = frontendManifest.modules.flatMap((module) => module.routes.map((route) => ({
  path: route.path.slice(1),
  name: route.name,
  component: loaders[route.component] ?? loaders.pending,
  meta: {
    title: route.title,
    roles: route.roles,
    capabilities: route.capabilities ?? module.capabilities,
    moduleId: module.id,
    runtime: module.runtime,
    migrationPending: module.state !== 'active',
  },
})))

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../../modules/auth/views/LoginView.vue'),
      meta: { title: 'Ingresar', public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/AppShell.vue'),
      children: moduleRoutes,
    },
    {
      path: '/403',
      name: 'forbidden',
      component: () => import('../../views/ForbiddenView.vue'),
      meta: { title: 'Acceso denegado', public: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/login' },
  ],
})

router.beforeEach(async (to) => {
  document.title = to.meta.title ? `${to.meta.title} | Growen` : 'Growen'
  if (to.meta.public) return true

  const auth = useAuthStore()
  await auth.hydrate()
  const access = resolveRouteAccess(to.meta.roles, auth.role, auth.isAuthenticated, to.meta.capabilities)

  if (access === 'login') return { name: 'login', query: { redirect: to.fullPath } }
  if (access === 'forbidden') return { name: 'forbidden' }
  return true
})
