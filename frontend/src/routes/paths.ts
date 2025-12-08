// NG-HEADER: Nombre de archivo: paths.ts
// NG-HEADER: Ubicación: frontend/src/routes/paths.ts
// NG-HEADER: Descripción: Constantes de rutas para react-router.
// NG-HEADER: Lineamientos: Ver AGENTS.md
export const PATHS = {
  home: "/",
  products: "/productos",
  productDetail: (id: number | string) => `/productos/${id}`,
  stock: "/stock",
  market: "/mercado",
  suppliers: "/proveedores",
  purchases: "/compras",
  purchasesNew: "/compras/nueva",
  // Clientes y Ventas
  customers: "/clientes",
  sales: "/ventas",
  // Admin
  admin: "/admin",
  adminUsers: "/admin/usuarios",
  adminServices: "/admin/servicios",
  adminImages: "/admin/imagenes-productos",
  adminDriveSync: "/admin/drive-sync",
  adminCatalogDiagnostics: "/admin/catalogos/diagnostico",
  adminBackups: "/admin/backups",
  adminScheduler: "/admin/scheduler",
  adminKnowledge: "/admin/cerebro",
  // legacy alias
  imagesAdmin: "/admin/imagenes",
} as const;

export type AppPath = typeof PATHS[keyof typeof PATHS];
