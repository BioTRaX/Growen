// NG-HEADER: Nombre de archivo: paths.ts
// NG-HEADER: Ubicación: frontend/src/routes/paths.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
export const PATHS = {
  home: "/",
  products: "/productos",
  productDetail: (id: number | string) => `/productos/${id}`,
  stock: "/stock",
  suppliers: "/proveedores",
  purchases: "/compras",
  purchasesNew: "/compras/nueva",
  // Admin
  admin: "/admin",
  adminUsers: "/admin/usuarios",
  adminServices: "/admin/servicios",
  adminImages: "/admin/imagenes-productos",
  // legacy alias
  imagesAdmin: "/admin/imagenes",
} as const;

export type AppPath = typeof PATHS[keyof typeof PATHS];
